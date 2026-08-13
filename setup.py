from setuptools import setup, find_packages
from typing import List

def get_requirement()->List[str]:
    requirement_lst:List[str]=[]
    with open('requirements.txt') as f:
        lines=f.readlines()
        for line in lines:
            package=line.strip()
            if package and package!='-e .':
                requirement_lst.append(package)
    return requirement_lst


setup(
    name='Ai-Security',
    version='0.0.1',
    description='A small package for dvc pipeline demo',
    author='Himanshu',
    license='MIT',
    packages=find_packages(),
    install_requires=get_requirement()
)