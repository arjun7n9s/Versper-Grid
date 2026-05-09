// DroneAnimator — Gazebo Harmonic (gz-sim8) system plugin
// Animates drone_d1/d2/d3 via direct ECM writes at sim rate.

#include <gz/sim/System.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/components/Pose.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/Model.hh>
#include <gz/plugin/Register.hh>
#include <gz/math/Pose3.hh>
#include <gz/math/Vector3.hh>
#include <gz/math/Quaternion.hh>
#include <gz/common/Console.hh>

#include <cmath>
#include <random>
#include <chrono>

namespace vesper
{
class DroneAnimator :
  public gz::sim::System,
  public gz::sim::ISystemConfigure,
  public gz::sim::ISystemPreUpdate
{
public:
  void Configure(const gz::sim::Entity &,
                 const std::shared_ptr<const sdf::Element> &,
                 gz::sim::EntityComponentManager &,
                 gz::sim::EventManager &) override
  {
    rng_.seed(std::random_device{}());
    PickNewD3Target();
    gzdbg << "[DroneAnimator] configured" << std::endl;
  }

  void PreUpdate(const gz::sim::UpdateInfo &_info,
                 gz::sim::EntityComponentManager &_ecm) override
  {
    if (_info.paused) return;
    const double t  = std::chrono::duration<double>(_info.simTime).count();
    const double dt = std::chrono::duration<double>(_info.dt).count();

    if (d1_ == gz::sim::kNullEntity) {
      d1_ = _ecm.EntityByComponents(gz::sim::components::Name("drone_d1"),
                                    gz::sim::components::Model());
      d2_ = _ecm.EntityByComponents(gz::sim::components::Name("drone_d2"),
                                    gz::sim::components::Model());
      d3_ = _ecm.EntityByComponents(gz::sim::components::Name("drone_d3"),
                                    gz::sim::components::Model());
      if (d1_ == gz::sim::kNullEntity) return;
      gzmsg << "[DroneAnimator] entities resolved d1=" << d1_
            << " d2=" << d2_ << " d3=" << d3_ << std::endl;
    }

    // D-1: hover with gentle bob
    {
      const double bob    = 0.25 * std::sin(t * 1.2);
      const double jitter = ((static_cast<int>(t * 2.0)) % 2 == 0) ? 0.04 : -0.04;
      SetPose(_ecm, d1_,
              72.0 + 0.4 * std::sin(t * 0.3),
              -50.0 + 0.4 * std::cos(t * 0.3),
              18.0 + bob + jitter,
              -2.4 + 0.05 * std::sin(t * 0.5));
    }

    // D-2: takeoff → patrol → land → idle
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

    // D-3: smooth random walk
    {
      const double dx   = d3_tgt_.X() - d3_pos_.X();
      const double dy   = d3_tgt_.Y() - d3_pos_.Y();
      const double dz   = d3_tgt_.Z() - d3_pos_.Z();
      const double dist = std::sqrt(dx*dx + dy*dy + dz*dz);
      if (dist < 3.0) {
        PickNewD3Target();
      } else {
        const double f = std::min(1.0, 5.0 * dt / dist);
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

  void PickNewD3Target() {
    std::uniform_real_distribution<double> dx(-80,80), dy(-80,80), dz(22,32);
    d3_tgt_ = gz::math::Vector3d(440.0 + dx(rng_), 30.0 + dy(rng_), dz(rng_));
  }

  static double Smoothstep(double t) { return t * t * (3.0 - 2.0 * t); }

  void SetPose(gz::sim::EntityComponentManager &_ecm,
               gz::sim::Entity _ent,
               double _x, double _y, double _z, double _yaw)
  {
    if (_ent == gz::sim::kNullEntity) return;
    gz::math::Pose3d pose(_x, _y, _z, 0, 0, _yaw);
    auto *comp = _ecm.Component<gz::sim::components::Pose>(_ent);
    if (comp) {
      *comp = gz::sim::components::Pose(pose);
      _ecm.SetChanged(_ent, gz::sim::components::Pose::typeId,
                      gz::sim::ComponentState::OneTimeChange);
    } else {
      _ecm.CreateComponent(_ent, gz::sim::components::Pose(pose));
    }
  }

  gz::sim::Entity d1_{gz::sim::kNullEntity};
  gz::sim::Entity d2_{gz::sim::kNullEntity};
  gz::sim::Entity d3_{gz::sim::kNullEntity};

  Phase  d2_phase_{Phase::Takeoff};
  double d2_phase_t_{0.0};

  gz::math::Vector3d d3_pos_{440.0, 30.0, 25.0};
  gz::math::Vector3d d3_tgt_{440.0, 30.0, 25.0};
  double d3_yaw_{1.2};

  std::mt19937 rng_;
};
}  // namespace vesper

GZ_ADD_PLUGIN(vesper::DroneAnimator,
              gz::sim::System,
              vesper::DroneAnimator::ISystemConfigure,
              vesper::DroneAnimator::ISystemPreUpdate)
GZ_ADD_PLUGIN_ALIAS(vesper::DroneAnimator, "vesper::DroneAnimator")
