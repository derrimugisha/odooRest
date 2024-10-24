from setuptools import setup, find_packages

setup(
    name="odooRest",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        'requests',
        'djangorestframework>=3.14.0',  # Added Django REST framework with version
        'django>=4.2.0',  # Added Django as it's required for DRF
    ],
    author="Derrick Mugisha",
    author_email="derrimugisha@gmail.com",
    description="A utility package that provides RESTful integration between Odoo and Django frameworks, enabling seamless communication and data synchronization between both platforms.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    # url="https://github.com/yourusername/my-utils",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Framework :: Django",  # Added Django framework classifier
        "Framework :: Django :: 4.2",  # Specify Django version support
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires='>=3.8',  # Specify minimum Python version
    keywords=['odoo', 'django', 'rest', 'api',
              'integration'],  # Added relevant keywords
)
