"""TODO."""

from distutils.core import setup

setup(
    name='nginx-access-tailer',
    version='0.1',
    author='swfrench',
    url='https://github.com/swfrench/nginx-tailer',
    packages=['nginx_access_tailer',],
    license='BSD three-clause license',
    entry_points={
        'console_scripts': ['nginx-access-tailer = nginx_access_tailer.__main__:main'],
    },
    install_requires=[
        'python-gflags >= 3.1.1',
        'google-cloud-monitoring >= 0.25.0',
    ],
)
