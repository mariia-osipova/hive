cmake_minimum_required(VERSION 3.20)
project(alphazero_hive LANGUAGES CXX)

option(HIVE_BUILD_TESTS "Build C++ engine tests" ON)
option(HIVE_BUILD_GUI "Build the copied SFML interface" OFF)
option(HIVE_BUILD_PYTHON "Build the pybind11 module" OFF)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(HIVE_ENGINE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/engine/team-cpp")
file(GLOB_RECURSE HIVE_CORE_SOURCES CONFIGURE_DEPENDS
    "${HIVE_ENGINE_DIR}/src/*.cpp")

add_library(hive_core STATIC ${HIVE_CORE_SOURCES})
add_library(hive::core ALIAS hive_core)
target_include_directories(hive_core PUBLIC "${HIVE_ENGINE_DIR}/include")
target_compile_features(hive_core PUBLIC cxx_std_17)
set_target_properties(hive_core PROPERTIES POSITION_INDEPENDENT_CODE ON)

add_executable(hive_bench "${CMAKE_CURRENT_SOURCE_DIR}/benchmarks/engine_benchmark.cpp")
target_link_libraries(hive_bench PRIVATE hive::core)

if(HIVE_BUILD_TESTS)
    enable_testing()
    find_package(GTest REQUIRED)
    file(GLOB HIVE_TEST_SOURCES CONFIGURE_DEPENDS "${HIVE_ENGINE_DIR}/tests/*.cpp")
    list(FILTER HIVE_TEST_SOURCES EXCLUDE REGEX "/hex_layout_test\\.cpp$")
    add_executable(hive_tests ${HIVE_TEST_SOURCES})
    target_include_directories(hive_tests PRIVATE "${HIVE_ENGINE_DIR}/tests")
    target_link_libraries(hive_tests PRIVATE hive::core GTest::gtest_main)
    include(GoogleTest)
    gtest_discover_tests(hive_tests)
endif()

if(HIVE_BUILD_GUI)
    find_package(SFML 2.5 COMPONENTS graphics window system REQUIRED)
    file(GLOB_RECURSE HIVE_GUI_SOURCES CONFIGURE_DEPENDS
        "${HIVE_ENGINE_DIR}/gui/*.cpp")
    add_executable(hive_gui ${HIVE_GUI_SOURCES})
    set_target_properties(hive_gui PROPERTIES OUTPUT_NAME hive)
    target_include_directories(hive_gui PRIVATE "${HIVE_ENGINE_DIR}/gui")
    target_link_libraries(hive_gui PRIVATE hive::core sfml-graphics sfml-window sfml-system)
    if(HIVE_BUILD_TESTS)
        add_executable(hive_gui_tests
            "${HIVE_ENGINE_DIR}/gui/HexLayout.cpp"
            "${HIVE_ENGINE_DIR}/tests/hex_layout_test.cpp")
        target_include_directories(hive_gui_tests PRIVATE
            "${HIVE_ENGINE_DIR}/gui" "${HIVE_ENGINE_DIR}/tests")
        target_link_libraries(hive_gui_tests PRIVATE hive::core GTest::gtest_main
            sfml-graphics sfml-window sfml-system)
        gtest_discover_tests(hive_gui_tests)
    endif()
endif()

if(HIVE_BUILD_PYTHON)
    find_package(pybind11 CONFIG REQUIRED)
    pybind11_add_module(_hive_cpp "${CMAKE_CURRENT_SOURCE_DIR}/bindings/python/module.cpp")
    target_link_libraries(_hive_cpp PRIVATE hive::core)
    install(TARGETS _hive_cpp LIBRARY DESTINATION alphazero_hive)
    add_custom_target(hive_python DEPENDS _hive_cpp)
endif()
