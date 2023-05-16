from cx_Freeze import setup, Executable

base = None

executables = [Executable("weatherly.py", base=base, icon='weather.ico')]

packages = [
    "idna",
    "os",
    "requests",
    "datetime",
    "pytz",
    "pandas",
    "pick",
    "alive_progress",
    "tkinter",
    "_tkinter",
    "webbrowser",
    "dotenv",
    "numpy",
    "geopy",
    "time"
]
options = {
    'build_exe': {
        'packages': packages,
    },
}

setup(
    name="Weatherly",
    options=options,
    version="2.0",
    description='A tool for completing meteorological data',
    executables=executables,
    icon='weather.ico',
    author='Matan and Tomer'
)
