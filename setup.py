from setuptools import setup


setup(
    name='cp4pc',
    version='0.1',
    author='Multiple Contributors',
    author_email='osbpau@gmail.com',  # should be email of pypi package maintainer
    description=(
        "A set of libraries designed to make a PC development environment "
        "look similar to the environment present on Digi's Connectport gateway "
        "products."),
    long_description=open('README.txt').read(),
    packages=[
        'rci',
    ],
    py_modules=[
        'addp',
        'cwm',
        'digicli',
        'idigidata',
        'simulator_settings',
        'xbee',
        'zigbee',
    ],
    # don't include webob, just mark as dependency
    install_requires=[
        'webob==1.2b3',
    ],
    license="MPL 2.0",
    url="https://github.com/jordanh/cp4pc",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
    ],
)
