import pathlib

from setuptools import find_packages, setup

here = pathlib.Path(__file__).parent.resolve()
long_description = (here / "README.md").read_text(encoding="utf-8")


setup(
    name="votomatico",
    version="1.0.0",
    description="Automatic voting bot for reality TV shows",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/grindlabs/votomatico",
    author="GrindLabs Softworks",
    author_email="contact@grindlabs.dev",
    keywords="reality shows, tv, cli, bot",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click",
        "hrequests",
        "beautifulsoup4",
    ],
    entry_points={
        "console_scripts": [
            "votomatico = votomatico.main:cli",
        ],
    },
)
