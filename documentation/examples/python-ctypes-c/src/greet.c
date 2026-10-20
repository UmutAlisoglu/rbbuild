// SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
// SPDX-FileContributor: Tolga Dalman
//
// SPDX-License-Identifier: MIT

#ifdef _WIN32
#  define GREET_API __declspec(dllexport)
#else
#  define GREET_API
#endif


GREET_API int greet_add(int a, int b) {
    return a + b;
}

GREET_API const char* greet_hello(void) {
    return "Hello from C";
}

