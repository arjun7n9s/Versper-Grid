cmake_minimum_required(VERSION 3.8)
project(lng_terminal_world)

find_package(ament_cmake REQUIRED)

install(DIRECTORY worlds launch materials
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS
  scripts/drone_animator.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
