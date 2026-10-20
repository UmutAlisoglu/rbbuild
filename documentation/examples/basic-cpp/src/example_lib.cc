// SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
// SPDX-FileContributor: Tolga Dalman
//
// SPDX-License-Identifier: MIT

#include "example_lib.h"

#include <iostream>

/*
    __PRETTY_FUNCTION__ is not portable:
    * GCC builtin
    * MSVC provides __FUNCSIG__
    * Fallback: __func__ shows the mangled C-style symbol names
*/
#ifndef __GNUC__
#ifdef __FUNCSIG__
#define __PRETTY_FUNCTION__ __FUNCSIG__
#else
#define __PRETTY_FUNCTION__ __func__
#endif
#endif

namespace rbbuild {

void ExampleLibrary::function() {

    std::cerr << "Calling " << __PRETTY_FUNCTION__ << std::endl;
}

}

