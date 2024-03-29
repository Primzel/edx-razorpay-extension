"""Setup for razorpay extension"""
import os

from setuptools import setup, find_packages


def package_data(package_roots):
    """Generic function to find package_data.
    All of the files under each of the `roots` will be declared as package
    data for package `pkg`.
    """
    data = []
    package_data = {}
    for pkg, roots in package_roots.items():
        for root in roots:
            for dirname, __, files in os.walk(os.path.join(pkg, root)):
                for fname in files:
                    data.append(os.path.relpath(os.path.join(dirname, fname), pkg))
        package_data[pkg] = data

    return package_data


def load_requirements(*requirements_paths):
    """
    Load all requirements from the specified requirements files.
    Returns a list of requirement strings.
    """
    requirements = set()
    for path in requirements_paths:
        with open(path) as reqs:
            requirements.update(
                line.split('#')[0].strip() for line in reqs
                if is_requirement(line.strip())
            )
    return list(requirements)


def is_requirement(line):
    """
    Return True if the requirement line is a package requirement;
    that is, it is not blank, a comment, a URL, or an included file.
    """
    return line and not line.startswith(('-r', '#', '-e', 'git+', '-c'))


with open('README.md') as _f:
    long_description = _f.read()

setup(
    name='edx-razorpay-extension',
    version='0.0.0',
    url='https://github.com/Primzel/edx-razorpay-extension',
    license='MIT',
    author='Qasim Gulzar',
    author_email='qasim@primzel.com',
    description='RazorPay integration extension for edX Ecommerce microservice.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    package_data=package_data({}),
    packages=find_packages(),
    install_requires=load_requirements('requirements/base.in'),
)
