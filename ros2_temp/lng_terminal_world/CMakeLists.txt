cmake_minimum_required(VERSION 3.8)
project(lng_terminal_world)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

find_package(ament_cmake REQUIRED)
find_package(gz-cmake3 REQUIRED)
find_package(gz-plugin2 REQUIRED COMPONENTS register)
find_package(gz-sim8 REQUIRED)
find_package(gz-math7 REQUIRED)
find_package(gz-common5 REQUIRED)

add_library(DroneAnimator SHARED plugins/DroneAnimator.cc)
target_link_libraries(DroneAnimator
  gz-sim8::gz-sim8
  gz-plugin2::register
  gz-math7::gz-math7
  gz-common5::gz-common5
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
