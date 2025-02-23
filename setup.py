from setuptools import setup, find_packages

setup(
    name="gnss_processor",
    version="0.1",
    packages=find_packages(),
    package_dir={'': '.'},
    install_requires=[
        'flask',
        'celery',
        'redis',
        'georinex',
        'pynmea2',
        'pandas',
        'python-dotenv',
        'openai>=1.0.0',
    ],
    python_requires='>=3.8',
) 