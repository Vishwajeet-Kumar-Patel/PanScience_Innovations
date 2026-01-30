@echo off
REM Coverage Report Generator for PanScience Innovations (Windows)
REM This script runs tests and generates HTML coverage report

echo 🧪 PanScience Innovations - Test Coverage Generator
echo ==================================================
echo.

REM Navigate to backend directory
cd backend

echo 📦 Installing test dependencies...
pip install -q pytest pytest-cov pytest-asyncio coverage-badge

echo.
echo 🧪 Running test suite with coverage...
pytest --cov=app --cov-report=html --cov-report=term-missing --cov-report=xml --cov-fail-under=95 -v

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ All tests passed! Coverage requirement met (95%+)
    echo.
    
    REM Generate coverage badge
    echo 🎨 Generating coverage badge...
    coverage-badge -o coverage.svg -f
    
    echo.
    echo 📊 Coverage Report Generated!
    echo    HTML Report: backend\htmlcov\index.html
    echo    XML Report:  backend\coverage.xml
    echo    Badge:       backend\coverage.svg
    echo.
    echo To view the HTML report, run:
    echo    start backend\htmlcov\index.html
    echo.
    
    REM Open the HTML report automatically
    start htmlcov\index.html
) else (
    echo.
    echo ❌ Tests failed or coverage below 95%%
    echo    Please fix failing tests or add more test coverage
    exit /b 1
)

cd ..
