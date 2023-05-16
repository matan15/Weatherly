import os
import requests as req
from datetime import datetime, timedelta
import pytz
import pandas as pd
from requests.exceptions import ConnectionError
from pick import pick
from alive_progress import alive_bar
from tkinter.filedialog import askopenfilename
import tkinter as tk
import _tkinter
import webbrowser
import dotenv
import numpy as np
import geopy.distance
import time

dotenv.load_dotenv(dotenv.find_dotenv())

headers = {'Authorization': os.environ.get('API_KEY')}


def menu():
    """
    Presents an in-terminal run menu.
    """
    title = 'Please choose an action:'
    options = ['read the documentation', 'update weather in file', 'exit']
    option, index = pick(options, title, indicator='=>', default_index=0)[0]
    return option


def distance(station, x, y):
    """
    Args:
        station (dict): A dictionary representing an IMS station, including its location (also a dictionary)
        x (float): The latitude value of a specific point
        y (float): The longitude value of a specific point
    Return:
        The geographic distance of a specific point from an IMS station (float).
    """
    try:
        return geopy.distance.geodesic((x, y), (station['location']['latitude'], station['location']['longitude'])).km
    except TypeError:
        return 999999


def get_timezone(d: datetime):
    """
    Args:
        d (Datetime object): A specific date and time.
    Return:
        The timezone, based on daytime or summertime.
    """
    israel = pytz.timezone('Israel').localize(d).strftime('%Y/%m/%d  %H:%M:%S %Z/%z').split('  ')
    return '+02:00' if 'IST' in israel[1] else '+03:00'


def round_timestamp(d: datetime, tz: str):
    """
    Args:
        d (Datetime object): A specific date and time.
        tz (str): Timezone of the country.
    Return:
        A timestamp, with the time rounded (str).
    """
    return f'{d.year}-{str(d.month).zfill(2)}-{str(d.day).zfill(2)}' \
           f'T{str(d.hour).zfill(2)}:{str(round(d.minute, 2)).zfill(2)}:00{tz}'


def next_day(d: datetime):
    """
    Args:
        d (Datetime object): A specific date.
    Return
        The following day to the specific date (Datetime object).
    """
    return d + timedelta(days=1)


def get_stations_json():
    """
    Return:
         A list containing all the data about current stations in a JSON format (list).
    """
    return get_response_json(f"{os.environ.get('URL')}/stations")


def get_response_json(url, params=None):
    """
    (Uses global headers)
    Args:
        url (str): A URL address to which the API request will be sent.
        params (str): Additional params to send with the API request. Default extra parameters are set to None.
    Return:
         A JSON object containing the response (dict).
    """
    response = req.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()


def parse_cord(d):
    """
    Args:
        d (str): Data contained in the 'coordination' column of a row, separated by a space or comma.
    Return:
        A list containing the two coordinates (list).
    """
    return [float(c.strip(' ')) for c in d.split(',' if ',' in d else ' ')]


def sort_samples(samples):
    """
    The function gets samples and groups them by station ID.
    Args:
        samples (list): A List of samples.
    Return:
        A list of the grouped samples (list).
    """
    with alive_bar(len(samples), ctrl_c=True, title='Sorting Samples') as bar:
        sample_by_stations = {}
        for sample in samples:
            if pd.isnull(sample['TD']) or pd.isnull(sample['TDmin']) or pd.isnull(sample['TDmax']) or pd.isnull(
                    sample['TG']) or pd.isnull(sample['WSmax']) or pd.isnull(sample['WDmax'])\
                    or pd.isnull(sample['WS']) or pd.isnull(sample['WD']) or pd.isnull(sample['STDwd'])\
                    or pd.isnull(sample['Grad']) or pd.isnull(sample['NIP']) or pd.isnull(sample['DiffR'])\
                    or pd.isnull(sample['RH']) or pd.isnull(sample['Rain']):
                if len(sample['stations']):
                    station_id = sample['stations'][0]['id']
                    if station_id not in sample_by_stations.keys():
                        sample_by_stations[station_id] = []
                    sample_by_stations[station_id].append(sample)
            bar()
    return sample_by_stations


def parse_table(df: pd.DataFrame, stations, radius):
    """
    The function converts a DataFrame into list of samples (list of dictionaries).
    The function puts in every sample the nearest stations in the radius that the user have entered.
    Args:
        df (DataFrame): A table with the date.
        stations (list): All the stations.
        radius (float): A specific radius to look within for stations.
    Return:
         A list of samples, formatted (list).
    """
    samples = []
    with alive_bar(len(df), ctrl_c=True, title='Parsing Table') as bar:
        rows = df.iterrows()
        for index, row in rows:
            date, time = str(row['Date']).split()
            date_split = date.split('-')
            time_split = time.split(':')
            dt = datetime(
                year=int(date_split[0]),
                month=int(date_split[1]),
                day=int(date_split[2]),
                hour=int(time_split[0]),
                minute=int(time_split[1]),
                second=int(time_split[2])
            )
            cord = parse_cord(row['Coordination'])
            data = {
                'index': index,
                'date': f'{dt.year}/{dt.month}/{dt.day}',
                'timestamp': round_timestamp(dt, get_timezone(dt)),
                'cord': cord,
                'TD': row['TD'],
                'TG': row['TG'],
                'TDmin': row['TDmin'],
                'TDmax': row['TDmax'],
                'WSmax': row['WSmax'],
                'WDmax': row['WDmax'],
                'WS': row['WS'],
                'WD': row['WD'],
                'STDwd': row['STDwd'],
                'Grad': row['Grad'],
                'NIP': row['NIP'],
                'DiffR': row['DiffR'],
                'RH': row['RH'],
                'Rain': row['Rain'],
                'stations': []
            }
            for station in stations:
                dis = distance(station, cord[0], cord[1])
                if dis <= radius:
                    data['stations'].append(dict(id=station['stationId'], dis=dis))
            data['stations'].sort(key=lambda a: a.get('dis'))
            samples.append(data)
            bar()
    return samples


def update(filepath, radius):
    """
    The function gets a file path and a radios to look for stations and updating the file.
    Args:
        filepath (str): path of the file to update.
        radius (float): radius to look for stations.
    """
    stations = get_stations_json()
    df = pd.read_excel(
        io=filepath,
        sheet_name='Sheet1') if filepath.endswith('xlsx') else pd.read_csv(
        filepath_or_buffer=filepath)
    if 'TD' not in df.columns and 'TDmin' not in df.columns and 'TDmax' not in df.columns and 'TG' not in df.columns and\
        'WSmax' not in df.columns and 'WDmax' not in df.columns and 'WS' not in df.columns and 'WD' not in df.columns \
        and 'STDwd' not in df.columns and 'Grad' not in df.columns and 'NIP' not in df.columns and\
        'DiffR' not in df.columns and 'RH' not in df.columns and 'Rain' not in df.columns:
        df.insert(loc=7, column='TD', value=pd.Series([np.nan for _ in range(len(df))]))
        df.insert(loc=8, column='TDmin', value=pd.Series([np.nan for _ in range(len(df))]))
        df.insert(loc=9, column='TDmax', value=pd.Series([np.nan for _ in range(len(df))]))
        df.insert(loc=10, column='TG', value=pd.Series([np.nan for _ in range(len(df))]))
        df.insert(loc=11, column='WSmax', value=pd.Series([np.nan for _ in range(len(df))]))
        df.insert(loc=12, column='WDmax', value=pd.Series([np.nan for _ in range(len(df))]))
        df.insert(loc=13, column='WS', value=pd.Series([np.nan for _ in range(len(df))]))
        df.insert(loc=14, column='WD', value=pd.Series([np.nan for _ in range(len(df))]))
        df.insert(loc=15, column='STDwd', value=pd.Series([np.nan for _ in range(len(df))]))
        df.insert(loc=16, column='Grad', value=pd.Series([np.nan for _ in range(len(df))]))
        df.insert(loc=17, column='NIP', value=pd.Series([np.nan for _ in range(len(df))]))
        df.insert(loc=18, column='DiffR', value=pd.Series([np.nan for _ in range(len(df))]))
        df.insert(loc=19, column='RH', value=pd.Series([np.nan for _ in range(len(df))]))
        df.insert(loc=20, column='Rain', value=pd.Series([np.nan for _ in range(len(df))]))

    df = df.sort_values(by='Date', ascending=True)
    samples = parse_table(df, stations, radius)
    while True:
        samples = sort_samples(samples)
        with alive_bar(len(samples), ctrl_c=True, title='Getting Information') as bar:
            for station_id in samples:
                first_date = samples[station_id][0]['date']
                year_last, month_last, day_last = samples[station_id][-1]['date'].split('/')
                last_date = next_day(datetime(year=int(year_last), month=int(month_last), day=int(day_last)))
                params = {
                    'from': first_date,
                    'to': f'{last_date.year}/{str(last_date.month).zfill(2)}/{str(last_date.day).zfill(2)}'
                }
                try:
                    response = req.get(url=f'{os.environ.get("URL")}/stations/{station_id}/data', params=params,
                                       headers=headers)
                except ConnectionError:
                    print('Connection error: Converting what I already have...')
                    df.to_excel(excel_writer=f'{filepath.split(".")[0]} updated.xlsx')
                    print(
                        f"The file was saved in the same directory of the original file as"
                        f" \"{filepath.split('.')[0]} updated.xlsx\"")
                    time.sleep(60)
                    exit(-1)
                if response.status_code == 200:
                    response = response.json()
                    for sample in samples[station_id]:
                        if pd.isnull(sample['TD']) or pd.isnull(sample['TDmin']) or pd.isnull(sample['TDmax']) \
                                or pd.isnull(sample['TG']) or pd.isnull(sample['WSmax']) or pd.isnull(sample['WDmax'])\
                                or pd.isnull(sample['WS']) or pd.isnull(sample['WD']) or pd.isnull(sample['STDwd'])\
                                or pd.isnull(sample['Grad']) or pd.isnull(sample['NIP']) or pd.isnull(sample['DiffR'])\
                                or pd.isnull(sample['RH']) or pd.isnull(sample['Rain']):
                            for data in response['data']:
                                if data['datetime'] == sample['timestamp']:
                                    for channel in data['channels']:
                                        if (channel['name'] == 'TD' or channel['name'] == 'TDmin' or channel[
                                            'name'] == 'TDmax' or channel['name'] == 'TG' or channel['name'] == 'WSmax'
                                            or channel['name'] == 'WDmax' or channel['name'] == 'WS'
                                            or channel['name'] == 'TG' or channel['name'] == 'WD'
                                            or channel['name'] == 'STDwd' or channel['name'] == 'Grad'
                                            or channel['name'] == 'NIP' or channel['name'] == 'DiffR'
                                            or channel['name'] == 'RH' or channel['name'] == 'Rain')\
                                            and channel['valid']:
                                            sample[channel['name']] = channel['value']
                bar()
        length = sum([len(samples[station_id]) for station_id in samples])
        with alive_bar(length, ctrl_c=True, title='Updating') as bar:
            for station_id in samples:
                for sample in samples[station_id]:
                    df.at[sample['index'], 'TD'] = sample['TD']
                    df.at[sample['index'], 'TDmin'] = sample['TDmin']
                    df.at[sample['index'], 'TDmax'] = sample['TDmax']
                    df.at[sample['index'], 'TG'] = sample['TG']
                    df.at[sample['index'], 'WSmax'] = sample['WSmax']
                    df.at[sample['index'], 'WDmax'] = sample['WDmax']
                    df.at[sample['index'], 'WS'] = sample['WS']
                    df.at[sample['index'], 'WD'] = sample['WD']
                    df.at[sample['index'], 'STDwd'] = sample['STDwd']
                    df.at[sample['index'], 'Grad'] = sample['Grad']
                    df.at[sample['index'], 'NIP'] = sample['NIP']
                    df.at[sample['index'], 'DiffR'] = sample['DiffR']
                    df.at[sample['index'], 'RH'] = sample['RH']
                    df.at[sample['index'], 'Rain'] = sample['Rain']
                    bar()
        empty_samples = []
        with alive_bar(length, ctrl_c=True, title='Collecting samples that haven\'t been updated') as bar:
            for station_id in samples:
                for sample in samples[station_id]:
                    if pd.isnull(sample['TD']) and pd.isnull(sample['TDmin']) and pd.isnull(sample['TDmax']) \
                            and pd.isnull(sample['TG']) and pd.isnull(sample['WSmax']) and pd.isnull(sample['WDmax'])\
                            and pd.isnull(sample['WS']) and pd.isnull(sample['WD']) and pd.isnull(sample['STDwd'])\
                            and pd.isnull(sample['Grad']) and pd.isnull(sample['NIP']) and pd.isnull(sample['DiffR'])\
                            and pd.isnull(sample['RH']) and pd.isnull(sample['Rain']):
                        _ = sample['stations'].pop(0)
                        if sample['stations']:
                            empty_samples.append(sample)
                    bar()
        if not empty_samples:
            break
        samples = empty_samples
    df.to_excel(excel_writer=f'{filepath.split(".")[0]} updated.xlsx')
    print(f"The file was saved in the same directory of the original file as \"{filepath.split('.')[0]} updated.xlsx\"")
    time.sleep(60)


if __name__ == '__main__':
    option = menu()
    if option == 'read the documentation':
        webbrowser.open(
            url="https://docs.google.com/document/d/1PlzrWxq807oAVeeqfVHyKQKRu8xGr697XgvDANgMd5g/edit?usp=sharing"
        )
    elif option == 'update weather in file':
        radius = float(input('Please enter in which radius do you want that the program will check for stations? '))
        root = tk.Tk()
        root.attributes('-topmost', True)
        root.withdraw()
        try:
            filepath = askopenfilename(
                filetypes=(
                    ("Excel Workbook", "*.xlsx"),
                    ("CSV UTF-8 (Comma delimited)", "*.csv"),
                    ("CSV (Comma delimited)", "*.csv"),
                    ("CSV (Macintosh)", "*.csv"),
                    ("CSV (MS-DOS)", "*.csv")
                )
            )
            root.destroy()
            update(filepath, radius)
        except _tkinter.TclError or FileNotFoundError:
            exit(1)
    elif option == 'exit':
        exit()
