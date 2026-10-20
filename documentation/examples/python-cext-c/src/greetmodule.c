// SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
// SPDX-FileContributor: Tolga Dalman
//
// SPDX-License-Identifier: MIT

#define PY_SSIZE_T_CLEAN
#include <Python.h>


static PyObject* greet_add(PyObject* Py_UNUSED(self), PyObject* args) {
    long a, b;
    if (!PyArg_ParseTuple(args, "ll", &a, &b))
        return NULL;
    return PyLong_FromLong(a + b);
}


static PyObject* greet_hello(PyObject* Py_UNUSED(self), PyObject* Py_UNUSED(ignored)) {
    return PyUnicode_FromString("Hello from C");
}


static PyMethodDef methods[] = {
    {"add",   greet_add,   METH_VARARGS, "Return a + b."},
    {"hello", greet_hello, METH_NOARGS,  "Return a greeting."},
    {NULL, NULL, 0, NULL}
};


static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT, "_greet", "Example extension module.", -1, methods,
    NULL, NULL, NULL, NULL
};


PyMODINIT_FUNC PyInit__greet(void) {
    return PyModule_Create(&module);
}

