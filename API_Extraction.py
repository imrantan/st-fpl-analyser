import requests
import pandas as pd
pd.set_option('display.max_columns', None)
from tqdm.auto import tqdm
tqdm.pandas()
import datetime
import pytz
import warnings

# Suppress all warnings
warnings.filterwarnings("ignore")

def run_api_extraction(game_week, league_id):
    """
    Extracts data from the Fantasy Premier League (FPL) API for a given league and game week.

    Parameters:
    - game_week: int, the maximum game week to extract data for.
    - league_id: int, the ID of the league to extract data for.

    Returns:
    - LEAGUE_NAME: str, the name of the league.
    - hist_Teams_data: DataFrame, historical team data.
    - Full_Selection_Data: DataFrame, team selection data with player points.
    - All_Transfers: DataFrame, transfer data including player information.
    - df_Transfers_IN_OUT: DataFrame, standardized transfer data for in and out players.
    """
    
    # Print the timestamp when the code starts
    start_time = datetime.datetime.now()
    print(f"Code started at: {start_time}")

    ### CONSTANTS ###
    BASE_URL = 'https://fantasy.premierleague.com/api/'
    LEAGUE_ID = int(league_id)
    MAX_GW = game_week
    print(f"EXTRACTING DATA UP TO GAME WEEK {MAX_GW}")

    ### Part 1 ###
    
    # 1. CREATE the dim_Teams table
    response = requests.get(BASE_URL + f'leagues-classic/{LEAGUE_ID}/standings/')
    if response.status_code == 200:
        df_standings = response.json()
    else:
        print(f"Failed to fetch data. Status code: {response.status_code}")
        print(response.text)
        return None, None, None, None, None

    LEAGUE_NAME = df_standings['league']['name']
    standings = pd.json_normalize(df_standings['standings']['results'])
    dim_Teams = standings[['id', 'player_name', 'entry', 'entry_name']]

    # 2. Create the preliminary hist_Teams_data table
    hist_Teams_data = pd.DataFrame()
    for entry in dim_Teams['entry']:
        df_history = requests.get(BASE_URL + f'entry/{entry}/history').json()
        historical_standings = pd.json_normalize(df_history['current'])
        historical_standings['entry'] = entry
        hist_Teams_data = pd.concat([hist_Teams_data, historical_standings])
        
    # 3. Merge dim_Teams and hist_Teams_data
    hist_Teams_data = pd.merge(left=dim_Teams, right=hist_Teams_data, left_on='entry', right_on='entry', how='left')
    
    # 4. Sorting within each 'event' group by 'total_points' and assigning rank
    hist_Teams_data['league_rank'] = hist_Teams_data.groupby('event')['total_points'].rank(method='dense', ascending=False).astype(int)

    ### PART 2 ###
    
    # 1. Create the All_TeamSelections DataFrame
    All_TeamSelections = pd.DataFrame()
    for GW in range(1, MAX_GW + 1):
        for entry in hist_Teams_data[hist_Teams_data['event'] == GW]['entry']:
            team_picks = requests.get(BASE_URL + f'entry/{entry}/event/{GW}/picks/').json()
            team_selection = pd.json_normalize(team_picks['picks'])
            team_selection['entry'] = entry
            team_selection['event'] = GW
            auto_subs = pd.json_normalize(team_picks['automatic_subs'])
            if auto_subs.empty:
                auto_subs = pd.DataFrame(columns=['entry', 'element_in', 'element_out', 'event'])
            team_selection = pd.merge(left=team_selection, right=auto_subs[['element_in', 'element_out']], left_on='element', right_on='element_in', how='left')
            team_selection = team_selection.drop('element_in', axis=1)
            team_selection = pd.merge(left=team_selection, right=auto_subs[['element_in', 'element_out']], left_on='element', right_on='element_out', how='left')
            team_selection = team_selection.drop('element_out_y', axis=1)
            team_selection.rename(columns={"element_out_x": "element_out"}, inplace=True)
            All_TeamSelections = pd.concat([All_TeamSelections, team_selection])

    # 2. Create the All_GW_data DataFrame
    All_GW_data = pd.DataFrame()
    for GW in range(1, MAX_GW + 1):
        game_week = requests.get(BASE_URL + f'event/{GW}/live/').json()
        elements = game_week['elements']
        temp_df = pd.DataFrame()
        for player in elements:
            temp_player = pd.json_normalize(player['stats'])
            temp_player['player_id'] = player['id']
            temp_df = pd.concat([temp_df, temp_player])
        temp_df['game_week'] = GW
        All_GW_data = pd.concat([All_GW_data, temp_df])

    # 3. Retrieve additional player and team information
    main_info = requests.get(BASE_URL + 'bootstrap-static/').json()
    main_player_info = pd.json_normalize(main_info['elements'])[[
        'id', 'element_type', 'first_name', 'second_name', 'web_name', 'team', 'team_code']]
    team_info = pd.json_normalize(main_info['teams'])[[
        'code', 'name', 'short_name', 'pulse_id']]
    element_types_info = pd.json_normalize(main_info['element_types'])[[
        'id', 'plural_name', 'plural_name_short', 'singular_name']]

    player_data = pd.merge(left=team_info, right=main_player_info, left_on='code', right_on='team_code', how='left', suffixes=('_team', '_player'))
    player_data = pd.merge(left=player_data, right=element_types_info, left_on='element_type', right_on='id', how='left', suffixes=('_player', '_position'))

    # 4. Merge All_Player_GW_data with player_data
    All_Player_GW_data = pd.merge(left=player_data, right=All_GW_data, left_on='id_player', right_on='player_id', how='left', suffixes=('_PLAYER', '_GW'))

    # 5. Merge All_TeamSelections with All_Player_GW_data
    Full_Selection_Data = pd.merge(left=All_TeamSelections, right=All_Player_GW_data, left_on=['event', 'element'], right_on=['game_week', 'player_id'], how='left', suffixes=('_TeamSelections', '_PlayerGW'))
    Full_Selection_Data = pd.merge(left=dim_Teams, right=Full_Selection_Data, left_on='entry', right_on='entry', how='left', suffixes=('_Team', '_Selection'))
    Full_Selection_Data['points_earned'] = Full_Selection_Data['multiplier'] * Full_Selection_Data['total_points']

    ### PART 3 ###

    # 1. Check for discrepancies in points data
    total_errors = 0
    for GW in range(1, MAX_GW + 1):
        print(f'\033[1mChecking for Game Week {GW} now...\033[0m')
        error_counter = 0
        for entry in dim_Teams['entry']:
            query_string = f"entry == {entry} and event == {GW}"
            player_name = dim_Teams[dim_Teams['entry'] == entry]['player_name'].iloc[0]
            hist_Teams_data_result = hist_Teams_data.query(query_string)
            Full_Selection_Data_result = Full_Selection_Data.query(query_string)
            hist_Teams_data_points = hist_Teams_data_result['points'].iloc[0] if not hist_Teams_data_result.empty else 0
            Full_Selection_Data_points = Full_Selection_Data_result['points_earned'].sum()
            if hist_Teams_data_points != Full_Selection_Data_points:
                print(f'ERROR identified for {player_name} Game Week {GW}.')
                print(f'Points from hist_Teams_data: {hist_Teams_data_points}')
                print(f'Points from Full_Selection_Data: {Full_Selection_Data_points}')
                error_counter += 1
        if error_counter > 0:
            print(f'\033[Total of {error_counter} errors noted for Game Week {GW}.\033[0m')
            total_errors += error_counter
        else:
            print(f'Checking done for Game Week {GW}.')

    ### PART 4 ###
    All_Transfers = pd.DataFrame()
    for entry in dim_Teams['entry']:
        df_transfers = requests.get(BASE_URL + f'entry/{entry}/transfers/').json()
        df_transfers = pd.json_normalize(df_transfers)
        All_Transfers = pd.concat([All_Transfers, df_transfers])

    All_Transfers = pd.merge(left=All_Transfers, right=dim_Teams, left_on='entry', right_on='entry', how='left')
    df_Transfers_IN_OUT = All_Transfers[['entry', 'element_in', 'element_out', 'event']].copy()

    # Print the timestamp when the code ends
    end_time = datetime.datetime.now()
    print(f"Code ended at: {end_time}")

    return LEAGUE_NAME, hist_Teams_data, Full_Selection_Data, All_Transfers, df_Transfers_IN_OUT