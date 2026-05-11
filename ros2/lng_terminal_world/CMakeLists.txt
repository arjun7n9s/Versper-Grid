cmake_minimum_required(VERSION 3.8)
project(lng_terminal_world)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

find_package(ament_cmake REQUIRED)
find_package(ignition-cmake2 REQUIRED)
find_package(ignition-plugin1 REQUIRED COMPONENTS register)
find_package(ignition-gazebo6 REQUIRED)
find_package(ignition-math6 REQUIRED)
find_package(ignition-common4 REQUIRED)

add_library(DroneAnimator SHARED plugins/DroneAnimator.cc)
target_link_libraries(DroneAnimator
  ignition-gazebo6::ignition-gazebo6
  ignition-plugin1::register
  ignition-math6::ignition-math6
  ignition-common4::ignition-common4
)

install(TARGETS DroneAnimator
  LIBRARY DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY worlds launch materials models
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS scripts/frame_sampler.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
