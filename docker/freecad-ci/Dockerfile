    && /opt/conda/envs/freecad/bin/python -m pip check \
    && /tmp/Tissu/build/bin/unit_tests --gtest_filter='MeshCollider.*:Solver.*' \
    && TISSU_FIX_SHA256="$(sha256sum /tmp/apply-tissu-contact-fix.py | awk '{print $1}')" \
    && TISSU_VERSION="$(/opt/conda/envs/freecad/bin/python -c "import importlib.metadata; print(importlib.metadata.version('pytissu'))")" \
    && TISSU_MODULE="$(/opt/conda/envs/freecad/bin/python -c "import tissu; print(tissu.__file__)")" \
    && printf '%s\n' \
         "tissu-source-repository=https://github.com/evanrock520-ciencias/Tissu.git" \
         "tissu-source-commit=$TISSU_SOURCE_COMMIT" \
         "tissu-contact-fix-sha256=$TISSU_FIX_SHA256" \
         "tissu-build=cmake-source" \
         "tissu-cpp-regression=MeshCollider.*:Solver.*" \
         "tissu-cpp-regression-result=passed" \
         "tissu-python-package-version=$TISSU_VERSION" \
         "tissu-python-module=$TISSU_MODULE" \
       > /opt/tissu-provenance.txt \
    && /opt/conda/envs/freecad/bin/python -c "import tissu, triangle, pytest; print('Tissu', tissu.__file__); print('Tissu source', '$TISSU_SOURCE_COMMIT'); print('Triangle', triangle.__file__); print('pytest', pytest.__version__)" \
    && mamba clean --all --yes \
    && mkdir -p /opt/freecad \
    && printf '%s\n' '#!/bin/sh' 'exec /opt/conda/envs/freecad/bin/freecad "$@"' > /opt/freecad/AppRun \
    && chmod +x /opt/freecad/AppRun
