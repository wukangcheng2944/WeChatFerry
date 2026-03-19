#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import print_function

from setuptools import find_packages, setup

import wcferry


with open("README.MD", "r", encoding="utf-8") as fh:
    long_description = fh.read()


setup(
    name="wcferry",
    version=wcferry.__version__,
    author="Changhua",
    author_email="lichanghua0821@gmail.com",
    description="Windows WeChat automation toolkit",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    url="https://github.com/wukangcheng2944/WeChatFerry",
    python_requires=">=3.8",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "setuptools",
        "grpcio-tools",
        "pynng",
        "requests",
        "openai",
        "python-dotenv",
        "psycopg[binary]",
    ],
    classifiers=[
        "Environment :: Win32 (MS Windows)",
        "Intended Audience :: Developers",
        "Intended Audience :: Customer Service",
        "Topic :: Communications :: Chat",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python",
    ],
    project_urls={
        "Documentation": "https://wechatferry.readthedocs.io/zh/latest/index.html",
        "GitHub": "https://github.com/wukangcheng2944/WeChatFerry/",
    },
)
