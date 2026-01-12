@echo off
REM Run tests with mocked Blender (fast)
pytest tests/ -v

REM To run tests in actual Blender (slow but accurate):
REM blender --background --python run_blender_tests.py -- tests/test_blender_integration/test_cameraframe.py -v -s
