cmake_minimum_required(VERSION 3.16)
project(lift_core_pybind LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(pybind11 REQUIRED)

pybind11_add_module(lift_core_pybind lift_core_bindings.cpp)
