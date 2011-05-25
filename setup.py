from setuptools import setup, find_packages
version = '0.1'

setup(name='Funnel',
      version=version,
      test_suite="nose.collector",
      tests_require="nose",
      description="Funnel is a tool for general performance/load tests",
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      entry_points={
        'console_scripts': [
            'funnel = funnel.loader:main',
            ],
        },

      )
