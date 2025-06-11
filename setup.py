# setup.py (đặt ở project root, bên cạnh folder k_dip/)
from setuptools import setup, find_packages

# Đọc dependencies thẳng từ requirements.txt
def load_requirements(path="requirements.txt"):
    with open(path) as f:
        reqs = []
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            reqs.append(line)
    return reqs

setup(
    name="k_dip",
    version="0.1.0",
    description="OCR + LLM document extraction pipeline",
    author="Your Name",
    author_email="you@example.com",
    python_requires=">=3.8",
    # 1) packages: thư mục k_dip/
    packages=find_packages(include=["k_dip", "k_dip.*"]),
    # 2) py_modules: các script .py ở root để console_scripts có thể import
    py_modules=[
        "marker_app",
        "marker_server",
        "chunk_convert",
        "convert",
        "convert_single",
        "extraction_app",
    ],
    install_requires=load_requirements("requirements.txt"),
    include_package_data=True,
    package_data={
        # copy cả thư mục static/fonts
        "": ["static/fonts/*.ttf"],
    },
    entry_points={
        "console_scripts": [
            # khi pip install xong, bạn có thể gọi trực tiếp:
            #   marker-app  -> launch streamlit App
            "marker-app=marker_app:streamlit_app_cli",
            "marker-server=marker_server:server_cli",
            "chunk-convert=chunk_convert:chunk_convert_cli",
            "convert=convert:convert_cli",
            "convert-single=convert_single:convert_single_cli",
            "extraction-app=extraction_app:extraction_app_cli",
        ]
    },
)
