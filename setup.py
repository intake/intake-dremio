#!/usr/bin/env python

from setuptools import setup, find_packages

import versioneer

extras_require = {
    'tests': [
        'pytest',
        'codecov',
        'pytest-cov',
        'flake8',
        'twine',
        'rfc3986',
        'keyring'
    ]
}

install_requires = [
    'pandas >=0.25',
    'intake',
    'pyarrow >=4.0'
]


setup_args = dict(
    name='intake-dremio',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description='Dremio plugin for Intake',
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url='https://github.com/philippjfr/intake-dremio',
    maintainer='Philipp Rudiger',
    maintainer_email='prudiger@anaconda.com',
    license='BSD-3',
    python_requires=">=3.6",
    py_modules=['intake_dremio'],
    packages=find_packages(),
    package_data={'': ['*.csv', '*.yml', '*.html']},
    entry_points={
        'intake.drivers': [
            'dremio = intake_dremio.intake_dremio:DremioSource'
        ]
    },
    include_package_data=True,
    install_requires=install_requires,
    extras_require=extras_require,
    zip_safe=False,
)

if __name__ == '__main__':
    setup(**setup_args)
