cmake_minimum_required(VERSION 3.22)
project(za6_description)

find_package(ament_cmake REQUIRED)
find_package(za6_tools REQUIRED)

install(
  DIRECTORY config launch meshes urdf test DESTINATION share/${PROJECT_NAME}
  )

if(BUILD_TESTING)

  find_package(ament_cmake_copyright REQUIRED)
  ament_copyright()

  find_package(ament_cmake_xmllint REQUIRED)
  ament_xmllint()

  find_package(ament_cmake_pep257 REQUIRED)
  ament_pep257()

  find_package(ament_cmake_pytest REQUIRED)
  foreach(gripper ${za6_tools_grippers})
    ament_add_pytest_test(
      za6_${gripper}_urdf_xacro test/test_za6_urdf_xacro.py ENV
      ZA_GRIPPER=${gripper}
      )
    ament_add_pytest_test(
      view_za6_${gripper}_launch test/test_view_za6_launch.py ENV
      ZA_GRIPPER=${gripper}
      )
  endforeach()
endif()

ament_package()
