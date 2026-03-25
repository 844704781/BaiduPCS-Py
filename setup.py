#!/usr/bin/env python

import os
from setuptools import setup, find_packages
from Cython.Build import cythonize
from distutils.command.build_ext import build_ext

# 定义 Cython 扩展
extensions = ["baidupcs_py/common/simple_cipher.pyx"]

# gcc arguments hack: enable optimizations
os.environ["CFLAGS"] = "-O3"

ext_modules = cythonize(
    extensions,
    language_level=3,
    compiler_directives={"linetrace": True},
)

if ext_modules:
    ext_modules[0].name = "baidupcs_py.common.simple_cipher"

setup(
    name="baidupcs-py",
    packages=find_packages(exclude=["imgs", "tests", "tests.*"]),
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
)
