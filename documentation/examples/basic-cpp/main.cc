// SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
// SPDX-FileContributor: Tolga Dalman
//
// SPDX-License-Identifier: MIT

#include "example_lib.h"
#include "basic_cpp_example_version.h"
#include <iostream>


int main() {
    std::cout << "This is the basic example program\n";
    std::cout << "Version string: " << basic_cpp_example_get_version_string() << "\n";
    std::cout << "git repository: " << basic_cpp_example_get_version_info()->git_repo << "\n";
    std::cout << "git HEAD hash: "  << basic_cpp_example_get_version_info()->git_hash << "\n";

    rbbuild::ExampleLibrary tl;

    tl.function();

    return 0;
}

