// DroneAnimator — Gazebo system plugin that runs inside the sim loop (1 kHz)
// and smoothly animates drone_d1 / drone_d2 / drone_d3 via direct ECM writes.
// Zero subprocess / network overhead → smooth 1000 Hz motion.

#include <ignition/gazebo/System.hh>
#include <ignition/gazebo/Model.hh>
#include <ignition/gazebo/Util.hh>
#include <ignition/gazebo/components/Pose.hh>
#include <ignition/gazebo/components/Name.hh>
#include <ignition/gazebo/components/Model.hh>
#include <ignition/plugin/Register.hh>
#include <ignition/math/Pose3.hh>
#include <ignition/math/Vector3.hh>
#include <ignition/math/Quaternion.hh>
#include <ignition/common/Console.hh>

#include <cmath>
#include <random>
#include <chrono>

namespace vesper
{
class DroneAnimator :
  public ignition::gazebo::System,
  public ignition::gazebo::ISystemConfigure,
  public ignition::gazebo::ISystemPreUpdate
{
public:
  void Configure(const ignition::gazebo::Entity &/*_entity*/,
                 const std::shared_ptr<const sdf::Element> &/*_sdf*/,
                 ignition::gazebo::EntityComponentManager &/*_ecm*/,
                 ignition::gazebo::EventManager &/*_eventMgr*/) override
  {
    rng_.seed(std::random_device{}());
    PickNewD3Target();
    igndbg << "[DroneAnimator] configured" << std::endl;
  }

  void PreUpdate(const ignition::gazebo::UpdateInfo &_info,
                 ignition::gazebo::EntityComponentManager &_ecm) override
  {
    if (_info.paused) return;
    const double t = std::chrono::duration<double>(_info.simTime).count();
    const double dt = std::chrono::duration<double>(_info.dt).count();

    // Resolve drone model entities once (cache)
    if (d1_ == ignition::gazebo::kNullEntity) {
      d1_ = _ecm.EntityByComponents(ignition::gazebo::components::Name("drone_d1"),
                                     ignition::gazebo::components::Model());
      d2_ = _ecm.EntityByComponents(ignition::gazebo::components::Name("drone_d2"),
                                     ignition::gazebo::components::Model());
      d3_ = _ecm.EntityByComponents(ignition::gazebo::components::Name("drone_d3"),
                                     ignition::gazebo::components::Model());
      if (d1_ == ignition::gazebo::kNullEntity) return;
      ignmsg << "[DroneAnimator] entities resolved d1=" << d1_
             << " d2=" << d2_ << " d3=" << d3_ << std::endl;
    }

    // ── D-1: hover with gentle bob + vertical micro-jitter for beacon blink
    {
      const bool blink = (static_cast<int>(t * 2.0)) % 2 == 0;
      const double bob = 0.25 * std::sin(t * 1.2);
      const double jitter = blink ? 0.04 : -0.04;
      const double x = 72.0 + 0.4 * std::sin(t * 0.3);
      const double y = -50.0 + 0.4 * std::cos(t * 0.3);
      const double z = 18.0 + bob + jitter;
      const double yaw = -2.4 + 0.05 * std::sin(t * 0.5);
      SetPose(_ecm, d1_, x, y, z, yaw);
    }

    // ── D-2: takeoff → patrol → land → idle, looped
    {
      d2_phase_t_ += dt;
      double x=0, y=10, z=0.18, yaw=0.4;
      switch (d2_phase_) {
        case Phase::Takeoff: {
          const double f = std::min(1.0, d2_phase_t_ / 4.0);
          z = 0.18 + (12.0 - 0.18) * Smoothstep(f);
          if (d2_phase_t_ > 4.0) { d2_phase_ = Phase::Patrol; d2_phase_t_ = 0; }
          break;
        }
        case Phase::Patrol: {
          const double ang = d2_phase_t_ * 0.4;
          x = 30.0 * std::cos(ang);
          y = 10.0 + 30.0 * std::sin(ang);
          z = 12.0 + 1.5 * std::sin(d2_phase_t_ * 0.8);
          yaw = ang + M_PI / 2.0;
          if (d2_phase_t_ > 16.0) { d2_phase_ = Phase::Land; d2_phase_t_ = 0; }
          break;
        }
        case Phase::Land: {
          const double f = std::min(1.0, d2_phase_t_ / 4.0);
          z = 12.0 - (12.0 - 0.18) * Smoothstep(f);
          if (d2_phase_t_ > 4.0) { d2_phase_ = Phase::Idle; d2_phase_t_ = 0; }
          break;
        }
        case Phase::Idle: {
          if (d2_phase_t_ > 3.0) { d2_phase_ = Phase::Takeoff; d2_phase_t_ = 0; }
          break;
        }
      }
      SetPose(_ecm, d2_, x, y, z, yaw);
    }

    // ── D-3: smooth random walk in Sector 2
    {
      const double dx = d3_tgt_.X() - d3_pos_.X();
      const double dy = d3_tgt_.Y() - d3_pos_.Y();
      const double dz = d3_tgt_.Z() - d3_pos_.Z();
      const double dist = std::sqrt(dx*dx + dy*dy + dz*dz);
      if (dist < 3.0) {
        PickNewD3Target();
      } else {
        const double speed = 5.0;
        const double step = speed * dt;
        const double f = std::min(1.0, step / dist);
        d3_pos_.X() += dx * f;
        d3_pos_.Y() += dy * f;
        d3_pos_.Z() += dz * f;
        d3_yaw_ = std::atan2(dy, dx);
      }
      SetPose(_ecm, d3_, d3_pos_.X(), d3_pos_.Y(), d3_pos_.Z(), d3_yaw_);
    }
  }

private:
  enum class Phase { Takeoff, Patrol, Land, Idle };

  void PickNewD3Target()
  {
    std::uniform_real_distribution<double> dx(-80, 80), dy(-80, 80), dz(22, 32);
    d3_tgt_ = ignition::math::Vector3d(440.0 + dx(rng_), 30.0 + dy(rng_), dz(rng_));
  }

  static double Smoothstep(double t)
  {
    return t * t * (3.0 - 2.0 * t);
  }

  void SetPose(ignition::gazebo::EntityComponentManager &_ecm,
               ignition::gazebo::Entity _ent,
               double _x, double _y, double _z, double _yaw)
  {
    if (_ent == ignition::gazebo::kNullEntity) return;
    ignition::math::Pose3d pose(
      _x, _y, _z,
      0, 0, _yaw);
    auto *comp = _ecm.Component<ignition::gazebo::components::Pose>(_ent);
    if (comp) {
      *comp = ignition::gazebo::components::Pose(pose);
      _ecm.SetChanged(_ent,
                      ignition::gazebo::components::Pose::typeId,
                      ignition::gazebo::ComponentState::OneTimeChange);
    } else {
      _ecm.CreateComponent(_ent, ignition::gazebo::components::Pose(pose));
    }
  }

  ignition::gazebo::Entity d1_{ignition::gazebo::kNullEntity};
  ignition::gazebo::Entity d2_{ignition::gazebo::kNullEntity};
  ignition::gazebo::Entity d3_{ignition::gazebo::kNullEntity};

  Phase d2_phase_{Phase::Takeoff};
  double d2_phase_t_{0.0};

  ignition::math::Vector3d d3_pos_{440.0, 30.0, 25.0};
  ignition::math::Vector3d d3_tgt_{440.0, 30.0, 25.0};
  double d3_yaw_{1.2};

  std::mt19937 rng_;
};
}  // namespace vesper

IGNITION_ADD_PLUGIN(vesper::DroneAnimator,
                    ignition::gazebo::System,
                    vesper::DroneAnimator::ISystemConfigure,
                    vesper::DroneAnimator::ISystemPreUpdate)
IGNITION_ADD_PLUGIN_ALIAS(vesper::DroneAnimator, "vesper::DroneAnimator")
