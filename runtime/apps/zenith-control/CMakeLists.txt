add_executable(zenith-control main.cpp)
target_link_libraries(zenith-control PRIVATE Threads::Threads)
target_compile_options(zenith-control PRIVATE -Wall -Wextra -Wpedantic)
target_compile_definitions(zenith-control PRIVATE
    ZENITH_VERSION="${PROJECT_VERSION}"
    ZENITH_PLATFORM="${ZENITH_PLATFORM}"
    ZENITH_COMPILER="${CMAKE_CXX_COMPILER_ID}-${CMAKE_CXX_COMPILER_VERSION}")
install(TARGETS zenith-control RUNTIME DESTINATION bin)

if(BUILD_TESTING AND NOT CMAKE_CROSSCOMPILING)
    add_test(NAME runtime-version COMMAND zenith-control --version)
    set_tests_properties(runtime-version PROPERTIES PASS_REGULAR_EXPRESSION "zenith-control ${PROJECT_VERSION}")
    add_test(NAME runtime-self-check COMMAND zenith-control --self-check)
    set_tests_properties(runtime-self-check PROPERTIES PASS_REGULAR_EXPRESSION "self-check: ok")
    add_test(NAME runtime-invalid-option COMMAND zenith-control --invalid)
    set_tests_properties(runtime-invalid-option PROPERTIES WILL_FAIL TRUE)
endif()
