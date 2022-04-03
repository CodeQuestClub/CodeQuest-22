import os.path
from setuptools import setup

REQUIRES_PYTHON = ">=3.6.0"

HERE = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(HERE, "README.md"), encoding="utf-8") as fid:
    README = fid.read()

with open(os.path.join(HERE, "requirements.txt")) as fid:
    REQUIREMENTS = [req for req in fid.read().split("\n") if req]

from codequest22 import __version__

setup(
    name="oaisudoiajsdoiausd",
    version=__version__,
    description="Game for Code Quest 2022",
    long_description=README,
    long_description_content_type="text/markdown",
    python_requires=REQUIRES_PYTHON,
    url="https://github.com/monash-programming-team/codequest22",
    author="Jackson Goerner, Ali Toosi",
    author_email="jgoerner@outlook.com, alitoosi137@gmail.com",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Development Status :: 4 - Beta",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Libraries :: pygame",
    ],
    packages=["codequest22"],
    include_package_data=True,
    install_requires=REQUIREMENTS,
    entry_points={
        "console_scripts": [
            "codequest22=codequest22:main",
        ]
    },
)
