cmake_minimum_required(VERSION 3.20)
project(qros_engine VERSION 0.6.0 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Runtime source identity: deterministic hash of files that define the executable semantics.
set(QROS_IDENTITY_FILES
    CMakeLists.txt
    cmake/build_identity.hpp.in
    include/qros/canonical_text.hpp
    include/qros/core.hpp
    include/qros/custody.hpp
    include/qros/qdata.hpp
    include/qros/research_contract.hpp
    include/qros/sha256.hpp
    include/qros/time_authority.hpp
    include/qros/text_snapshot.hpp
    src/core.cpp
    src/custody.cpp
    src/qdata.cpp
    src/research_contract.cpp
    src/sha256.cpp
    src/time_authority.cpp
    src/text_snapshot.cpp
    include/qros/pipeline.hpp
    include/qros/mt5_template.hpp
    src/pipeline_common.cpp
    src/pipeline_data.cpp
    src/feature_graph.cpp
    src/universe.cpp
    src/backtest.cpp
    src/result_store.cpp
    src/gates.cpp
    src/vault.cpp
    src/portfolio.cpp
    src/pipeline_cli.cpp
    src/mt5_bridge.cpp
    scripts/build_native.py
    src/main.cpp)
set(QROS_CONFIGURE_DEPENDS_FILES "")
foreach(rel IN LISTS QROS_IDENTITY_FILES)
    list(APPEND QROS_CONFIGURE_DEPENDS_FILES "${CMAKE_SOURCE_DIR}/${rel}")
endforeach()
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${QROS_CONFIGURE_DEPENDS_FILES})

set(QROS_SOURCE_ROOT_INPUT "QROS_SOURCE_ROOT_V1\n")
foreach(rel IN LISTS QROS_IDENTITY_FILES)
    file(SHA256 "${CMAKE_SOURCE_DIR}/${rel}" h)
    string(APPEND QROS_SOURCE_ROOT_INPUT "${rel}=${h}\n")
endforeach()
string(SHA256 QROS_SOURCE_ROOT_SHA256 "${QROS_SOURCE_ROOT_INPUT}")

# Build contract is separate from source identity: same sources compiled with different
# profiles/flags remain distinguishable even before examining the executable SHA-256.
string(TOUPPER "${CMAKE_BUILD_TYPE}" QROS_BUILD_TYPE_UPPER)
set(QROS_BUILD_TYPE_FLAGS "${CMAKE_CXX_FLAGS_${QROS_BUILD_TYPE_UPPER}}")
set(QROS_BUILD_CONTRACT_INPUT "QROS_BUILD_CONTRACT_V1\n")
string(APPEND QROS_BUILD_CONTRACT_INPUT "build_type=${CMAKE_BUILD_TYPE}\n")
string(APPEND QROS_BUILD_CONTRACT_INPUT "compiler_id=${CMAKE_CXX_COMPILER_ID}\n")
string(APPEND QROS_BUILD_CONTRACT_INPUT "compiler_version=${CMAKE_CXX_COMPILER_VERSION}\n")
string(APPEND QROS_BUILD_CONTRACT_INPUT "system_name=${CMAKE_SYSTEM_NAME}\n")
string(APPEND QROS_BUILD_CONTRACT_INPUT "system_processor=${CMAKE_SYSTEM_PROCESSOR}\n")
string(APPEND QROS_BUILD_CONTRACT_INPUT "cxx_flags=${CMAKE_CXX_FLAGS}\n")
string(APPEND QROS_BUILD_CONTRACT_INPUT "build_type_flags=${QROS_BUILD_TYPE_FLAGS}\n")
string(APPEND QROS_BUILD_CONTRACT_INPUT "exe_linker_flags=${CMAKE_EXE_LINKER_FLAGS}\n")
string(SHA256 QROS_BUILD_CONTRACT_SHA256 "${QROS_BUILD_CONTRACT_INPUT}")
file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/generated/qros")
configure_file(cmake/build_identity.hpp.in "${CMAKE_BINARY_DIR}/generated/qros/build_identity.hpp" @ONLY)

add_library(qros_core src/core.cpp src/custody.cpp src/qdata.cpp src/research_contract.cpp src/sha256.cpp src/time_authority.cpp src/text_snapshot.cpp src/pipeline_common.cpp src/pipeline_data.cpp src/feature_graph.cpp src/universe.cpp src/backtest.cpp src/result_store.cpp src/gates.cpp src/vault.cpp src/portfolio.cpp src/pipeline_cli.cpp src/mt5_bridge.cpp)
target_include_directories(qros_core PUBLIC include "${CMAKE_BINARY_DIR}/generated")
target_compile_options(qros_core PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow -Werror)
target_compile_definitions(qros_core PRIVATE _GLIBCXX_ASSERTIONS)

add_executable(qros src/main.cpp)
target_link_libraries(qros PRIVATE qros_core)
target_compile_options(qros PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow -Werror)
target_compile_definitions(qros PRIVATE _GLIBCXX_ASSERTIONS)

add_executable(qros_tests tests/test_core.cpp)
target_link_libraries(qros_tests PRIVATE qros_core)
target_compile_options(qros_tests PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow -Werror)
target_compile_definitions(qros_tests PRIVATE _GLIBCXX_ASSERTIONS)

enable_testing()
add_test(NAME qros_tests COMMAND qros_tests)

add_executable(qros_product_contract_tests tests/test_product_contract.cpp)
target_link_libraries(qros_product_contract_tests PRIVATE qros_core)
target_compile_options(qros_product_contract_tests PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow -Werror)
target_compile_definitions(qros_product_contract_tests PRIVATE _GLIBCXX_ASSERTIONS)
add_test(NAME qros_product_contract_tests COMMAND qros_product_contract_tests)

# Metadata-governance test only; the runtime itself has no Python dependency.
find_package(Python3 COMPONENTS Interpreter QUIET)
if(Python3_Interpreter_FOUND)
    add_test(
        NAME active_data_authorities
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/tests/check_active_authorities.py")
else()
    message(FATAL_ERROR "Python3 interpreter required to execute authority-regression tests")
endif()

add_executable(qros_pipeline_tests tests/test_pipeline.cpp)
target_link_libraries(qros_pipeline_tests PRIVATE qros_core)
target_compile_options(qros_pipeline_tests PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow -Werror)
target_compile_definitions(qros_pipeline_tests PRIVATE _GLIBCXX_ASSERTIONS)
add_test(NAME qros_pipeline_tests COMMAND qros_pipeline_tests)

# The recovered archive lacked these synthetic fixtures. Generate, never forge,
# their custody receipts with the exact binary used by this test configuration.
set(QROS_TEST_FIXTURE_DIR "${CMAKE_BINARY_DIR}/fixtures-${QROS_BUILD_CONTRACT_SHA256}")
add_test(NAME prepare_synthetic_fixtures COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_SOURCE_DIR}/tests/prepare_fixtures.py" "$<TARGET_FILE:qros>" "${QROS_TEST_FIXTURE_DIR}")
set_tests_properties(prepare_synthetic_fixtures PROPERTIES FIXTURES_SETUP qros_synthetic)
foreach(suite parity_randomized qdata_parity_randomized qdata_negative_cases custody_negative_cases custody_parity_randomized time_authority_negative_cases time_authority_parity_randomized)
    add_test(NAME "${suite}" COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/tests/${suite}.py"
        "$<TARGET_FILE:qros>" "${QROS_TEST_FIXTURE_DIR}")
    set_tests_properties("${suite}" PROPERTIES FIXTURES_REQUIRED qros_synthetic TIMEOUT 120)
endforeach()
add_test(NAME pipeline_integration COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_SOURCE_DIR}/tests/test_pipeline_integration.py" "$<TARGET_FILE:qros>"
    --out "${CMAKE_BINARY_DIR}/integration-evidence" --fresh-run)
set_tests_properties(pipeline_integration PROPERTIES TIMEOUT 120)
