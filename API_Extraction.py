import requests
import pandas as pd
import datetime
import pytz
import warnings
from tqdm.auto import tqdm

# Suppress all warnings
warnings.filterwarnings("ignore")

# Set pandas display options
pd.set_option('display.max_columns', None)
tqdm.pandas()

# Constants
BASE_URL = 'https://fantasy.premierleague.com/api/'

def fetch_data(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch data. Status code: {response.status_code}")
        print(response.text)
        return None

def create_dim_teams(league_id):
    url = f"{BASE_URL}leagues-classic/{league_id}/standings/"
    data = fetch_data(url)    
    league_name = data['league']['name']
    standings = pd.json_normalize(data['standings']['results'])
    return standings[['id', 'player_name', 'entry', 'entry_name']], league_name

def create_hist_teams_data(dim_teams):
    hist_teams_data = pd.DataFrame()
    for entry in dim_teams['entry']:
        url = f"{BASE_URL}entry/{entry}/history"
        data = fetch_data(url)
        if data:
            historical_standings = pd.json_normalize(data['current'])
            historical_standings['entry'] = entry
            hist_teams_data = pd.concat([hist_teams_data, historical_standings])
    
    hist_teams_data = pd.merge(dim_teams, hist_teams_data, on='entry', how='left')
    hist_teams_data['league_rank'] = hist_teams_data.groupby('event')['total_points'].rank(method='dense', ascending=False).astype(int)
    return hist_teams_data

def create_all_team_selections(hist_teams_data, max_gw):
    all_team_selections = pd.DataFrame()
    for gw in range(1, max_gw + 1):
        for entry in hist_teams_data[hist_teams_data['event'] == gw]['entry']:
            url = f"{BASE_URL}entry/{entry}/event/{gw}/picks/"
            data = fetch_data(url)
            if data:
                team_selection = pd.json_normalize(data['picks'])
                team_selection['entry'] = entry
                team_selection['event'] = gw
                auto_subs = pd.json_normalize(data['automatic_subs'])
                
                if auto_subs.empty:
                    auto_subs = pd.DataFrame(columns=['entry', 'element_in', 'element_out', 'event'])
                
                team_selection = pd.merge(team_selection, auto_subs[['element_in', 'element_out']], 
                                          left_on='element', right_on='element_in', how='left')
                team_selection = team_selection.drop('element_in', axis=1)
                team_selection = pd.merge(team_selection, auto_subs[['element_in', 'element_out']], 
                                          left_on='element', right_on='element_out', how='left')
                team_selection = team_selection.drop('element_out_y', axis=1)
                team_selection.rename(columns={"element_out_x": "element_out"}, inplace=True)
                
                all_team_selections = pd.concat([all_team_selections, team_selection])
    return all_team_selections

def create_all_gw_data(max_gw):
    all_gw_data = pd.DataFrame()
    for gw in range(1, max_gw + 1):
        url = f"{BASE_URL}event/{gw}/live/"
        data = fetch_data(url)
        if data:
            elements = data['elements']
            temp_df = pd.DataFrame()
            for player in elements:
                temp_player = pd.json_normalize(player['stats'])
                temp_player['player_id'] = player['id']
                temp_df = pd.concat([temp_df, temp_player])
            temp_df['game_week'] = gw
            all_gw_data = pd.concat([all_gw_data, temp_df])
    return all_gw_data

def get_player_info():
    url = f"{BASE_URL}bootstrap-static/"
    data = fetch_data(url)
    if data:
        main_player_info = pd.json_normalize(data['elements'])
        important_columns = ['id', 'element_type', 'first_name', 'second_name', 'web_name', 'team', 'team_code']
        main_player_info = main_player_info[important_columns]
        
        team_info = pd.json_normalize(data['teams'])
        team_info = team_info[['code', 'name', 'short_name', 'pulse_id']]
        
        element_types_info = pd.json_normalize(data['element_types'])
        element_types_info = element_types_info[['id', 'plural_name', 'plural_name_short', 'singular_name']]
        
        player_data = pd.merge(team_info, main_player_info, left_on='code', right_on='team_code', how='left', suffixes=('_team', '_player'))
        player_data = pd.merge(player_data, element_types_info, left_on='element_type', right_on='id', how='left', suffixes=('_player', '_position'))
        
        return player_data
    return None

def merge_data(player_data, all_gw_data, all_team_selections, dim_teams):
    all_player_gw_data = pd.merge(player_data, all_gw_data, left_on='id_player', right_on='player_id', how='left', suffixes=('_PLAYER', '_GW'))
    full_selection_data = pd.merge(all_team_selections, all_player_gw_data, left_on=['event', 'element'], right_on=['game_week', 'player_id'], how='left', suffixes=('_TeamSelections', '_PlayerGW'))
    full_selection_data = pd.merge(dim_teams, full_selection_data, on='entry', how='left', suffixes=('_Team', '_Selection'))
    full_selection_data['points_earned'] = full_selection_data['multiplier'] * full_selection_data['total_points']
    return full_selection_data

def check_data_consistency(dim_teams, hist_teams_data, full_selection_data, max_gw):
    total_errors = 0
    for gw in range(1, max_gw + 1):
        print(f'\033[1mChecking for Game Week {gw} now...\033[0m')
        error_counter = 0
        for entry in dim_teams['entry']:
            query_string = f"entry == {entry} and event == {gw}"
            player_name = dim_teams[dim_teams['entry'] == entry]['player_name'].iloc[0]
            hist_teams_data_result = hist_teams_data.query(query_string)
            full_selection_data_result = full_selection_data.query(query_string)
            
            hist_teams_data_points = hist_teams_data_result['points'].iloc[0] if not hist_teams_data_result.empty else 0
            full_selection_data_points = full_selection_data_result['points_earned'].sum()

            if hist_teams_data_points != full_selection_data_points:
                print(f'ERROR identified for {player_name} Game Week {gw}.')
                print(f'Points from hist_Teams_data: {hist_teams_data_points}')
                print(f'Points from Full_Selection_Data: {full_selection_data_points}')
                error_counter += 1
        
        if error_counter > 0:
            print(f'\033[1mTotal of {error_counter} errors noted for Game Week {gw}.\033[0m')
            total_errors += error_counter
        else:
            print(f'Checking done for Game Week {gw}.')
    return total_errors

def get_all_transfers(dim_teams, max_gw):
    all_transfers = pd.DataFrame()
    for entry in dim_teams['entry']:
        url = f"{BASE_URL}entry/{entry}/transfers/"
        data = fetch_data(url)
        if data:
            df_transfers = pd.json_normalize(data)
            all_transfers = pd.concat([all_transfers, df_transfers])
    
    all_transfers = all_transfers[all_transfers['event'] <= max_gw]
    all_transfers['element_in_cost'] = all_transfers['element_in_cost'] / 10
    all_transfers['element_out_cost'] = all_transfers['element_out_cost'] / 10
    all_transfers['time'] = pd.to_datetime(all_transfers['time'])
    
    sgt_timezone = pytz.timezone('Asia/Singapore')
    all_transfers['time_SG'] = all_transfers['time'].dt.tz_convert(sgt_timezone)
    all_transfers['date_clean'] = all_transfers['time_SG'].dt.date
    all_transfers['time_clean'] = all_transfers['time_SG'].dt.time
    
    return all_transfers

def process_transfers(all_transfers, dim_teams, player_data, hist_teams_data, all_gw_data):
    all_transfers = pd.merge(all_transfers, dim_teams, on='entry', how='left', suffixes=('_Team', '_Transfer'))
    all_transfers = pd.merge(all_transfers, player_data, left_on='element_in', right_on='id_player', how='left', suffixes=('_Team', '_PlayerIn'))
    all_transfers = pd.merge(all_transfers, player_data, left_on='element_out', right_on='id_player', how='left', suffixes=('_PlayerIn', '_PlayerOut'))
    
    hist_teams_data_lite = hist_teams_data[['entry', 'event', 'league_rank']]
    all_transfers = pd.merge(all_transfers, hist_teams_data_lite, on=['event', 'entry'], how='left')
    
    all_transfers.reset_index(inplace=True)
    all_transfers['Transfer_ID'] = all_transfers.index
    
    common_columns = ['entry', 'event', 'league_rank', 'time', 'id', 'player_name', 'entry_name', 'time_SG', 'date_clean', 'time_clean', 'Transfer_ID']
    columns_for_player_in = ['element_in', 'element_in_cost', 'name_PlayerIn', 'id_player_PlayerIn', 'first_name_PlayerIn', 'second_name_PlayerIn', 'web_name_PlayerIn', 'singular_name_PlayerIn']
    columns_for_player_out = ['element_out', 'element_out_cost', 'name_PlayerOut', 'id_player_PlayerOut', 'first_name_PlayerOut', 'second_name_PlayerOut', 'web_name_PlayerOut', 'singular_name_PlayerOut']
    standardised_columns = ['element', 'element_cost', 'name', 'id_player', 'first_name', 'second_name', 'web_name', 'singular_name']
    
    df_transfer_ins = all_transfers[common_columns + columns_for_player_in]
    df_transfer_outs = all_transfers[common_columns + columns_for_player_out]
    
    df_transfer_ins.columns = common_columns + standardised_columns
    df_transfer_outs.columns = common_columns + standardised_columns
    
    df_transfer_ins['Direction'] = 'In'
    df_transfer_outs['Direction'] = 'Out'
    
    df_transfers_in_out = pd.concat([df_transfer_ins, df_transfer_outs])
    
    all_gw_data_lite = all_gw_data[['game_week', 'player_id', 'total_points']]
    df_transfers_in_out = pd.merge(df_transfers_in_out, all_gw_data_lite, left_on=['event', 'id_player'], right_on=['game_week', 'player_id'], how='left')
    
    return df_transfers_in_out

def run_api_extraction(game_week, league_id):
    start_time = datetime.datetime.now()
    print(f"Code started at: {start_time}")
    
    print(f"EXTRACTING DATA UP TO GAME WEEK {game_week}")
    
    dim_teams, league_name = create_dim_teams(league_id)
    if dim_teams is None:
        return None, None, None, None, None
    
    hist_teams_data = create_hist_teams_data(dim_teams)
    all_team_selections = create_all_team_selections(hist_teams_data, game_week)
    all_gw_data = create_all_gw_data(game_week)
    player_data = get_player_info()
    
    full_selection_data = merge_data(player_data, all_gw_data, all_team_selections, dim_teams)
    
    total_errors = check_data_consistency(dim_teams, hist_teams_data, full_selection_data, game_week)
    print(f"Total errors found: {total_errors}")
    
    all_transfers = get_all_transfers(dim_teams, game_week)
    df_transfers_in_out = process_transfers(all_transfers, dim_teams, player_data, hist_teams_data, all_gw_data)
    
    end_time = datetime.datetime.now()
    print(f"Code ended at: {end_time}")
    
    elapsed_time = end_time - start_time
    hours, remainder = divmod(elapsed_time.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    elapsed_time_formatted = f"{hours:02}:{minutes:02}:{seconds:02}"
    print(f"Elapsed time: {elapsed_time_formatted}")
    
    return league_name, hist_teams_data, full_selection_data, all_transfers, df_transfers_in_out