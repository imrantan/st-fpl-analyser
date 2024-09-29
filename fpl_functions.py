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

### START OF API RELATED FUNCTIONS ###

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
    start_event = data['league']['start_event'] # some leagues starts from a later week
    # standings.rename(columns={"rank": "league_rank"}, inplace=True) # rename rank column to league_rank
    return standings[['id', 'player_name', 'entry', 'entry_name']], league_name, start_event

def create_hist_teams_data(dim_teams, start_event):
    hist_teams_data = pd.DataFrame()
    for entry in dim_teams['entry']:
        url = f"{BASE_URL}entry/{entry}/history"
        data = fetch_data(url)
        if data:
            historical_standings = pd.json_normalize(data['current'])
            historical_standings['entry'] = entry
            hist_teams_data = pd.concat([hist_teams_data, historical_standings])

    # Ensure that the dataset only starts from the start_event gameweek
    hist_teams_data = hist_teams_data[hist_teams_data['event']>=start_event]
    hist_teams_data = pd.merge(dim_teams, hist_teams_data, on='entry', how='left')

    # Sort by 'entry_name' and 'event' to ensure proper order for cumulative sum
    hist_teams_data = hist_teams_data.sort_values(by=['entry_name', 'event'])

    # get the net points
    hist_teams_data['gw_points'] = hist_teams_data['points'] - hist_teams_data['event_transfers_cost']

    # Perform cumulative sum of 'points' within each 'entry_name' group, ordered by 'event'
    hist_teams_data['total_points'] = hist_teams_data.groupby('entry_name')['gw_points'].cumsum()

    hist_teams_data['league_rank'] = hist_teams_data.groupby('event')['total_points'].rank(method='dense', ascending=False).astype(int)
    
    return hist_teams_data

def create_all_team_selections(hist_teams_data, max_gw, start_event):
    all_team_selections = pd.DataFrame()
    for gw in range(start_event, max_gw + 1):
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

def create_all_gw_data(max_gw, start_event):
    all_gw_data = pd.DataFrame()
    for gw in range(start_event, max_gw + 1):
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

def check_data_consistency(dim_teams, hist_teams_data, full_selection_data, max_gw, start_event):
    total_errors = 0
    for gw in range(start_event, max_gw + 1):
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

def get_all_transfers(dim_teams, max_gw, start_event):
    all_transfers = pd.DataFrame()
    for entry in dim_teams['entry']:
        url = f"{BASE_URL}entry/{entry}/transfers/"
        data = fetch_data(url)
        if data:
            df_transfers = pd.json_normalize(data)
            all_transfers = pd.concat([all_transfers, df_transfers])
    
    all_transfers = all_transfers[(all_transfers['event'] <= max_gw) 
                                  & (all_transfers['event'] >= start_event)]

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
    
    return all_transfers, df_transfers_in_out

def run_api_extraction(game_week, league_id):
    start_time = datetime.datetime.now()
    print(f"Code started at: {start_time}")
    
    print(f"EXTRACTING DATA UP TO GAME WEEK {game_week}")
    
    dim_teams, league_name, start_event = create_dim_teams(league_id)
    if dim_teams is None:
        return None, None, None, None, None
    
    hist_teams_data = create_hist_teams_data(dim_teams, start_event)
    all_team_selections = create_all_team_selections(hist_teams_data, game_week, start_event)
    all_gw_data = create_all_gw_data(game_week, start_event)
    player_data = get_player_info()
    
    full_selection_data = merge_data(player_data, all_gw_data, all_team_selections, dim_teams)
    
    total_errors = check_data_consistency(dim_teams, hist_teams_data, full_selection_data, game_week, start_event)
    print(f"Total errors found: {total_errors}")
    
    all_transfers = get_all_transfers(dim_teams, game_week, start_event)
    all_transfers, df_transfers_in_out = process_transfers(all_transfers, dim_teams, player_data, hist_teams_data, all_gw_data)
    
    end_time = datetime.datetime.now()
    print(f"Code ended at: {end_time}")
    
    elapsed_time = end_time - start_time
    hours, remainder = divmod(elapsed_time.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    elapsed_time_formatted = f"{hours:02}:{minutes:02}:{seconds:02}"
    print(f"Elapsed time: {elapsed_time_formatted}")
    
    return league_name, start_event, hist_teams_data, full_selection_data, all_transfers, df_transfers_in_out

### END OF API RELATED FUNCTIONS ###



### START OF ANALYTICAL FUNCTIONS ###

def cleanse_similar_df(df, team_1, team_2):
    """
    Format the table to display all the players that are similar between the 2 teams.
    """
    if df.empty:
        return pd.DataFrame(columns=['Player ID', 'Player Name',            
                                     f'{team_1} Selection', f'{team_2} Selection',            
                                     f'Captained by {team_1}', f'Captained by {team_2}',             
                                     f'Vice-capt by {team_1}', f'Vice-capt by {team_2}'
                                     ])

    # make a copy
    similar_df = df.copy()

    similar_df = similar_df[['player_id', 'web_name_1', 'position_1', 'position_2', 
                         'is_captain_1', 'is_captain_2', 'is_vice_captain_1', 'is_vice_captain_2']]
 
    # Assuming your dataframe is named 'df'
    columns_to_replace = ['is_captain_1', 'is_captain_2', 'is_vice_captain_1', 'is_vice_captain_2']

    # Replace True with 'Yes' and False with 'No' in the specified columns
    similar_df[columns_to_replace] = similar_df[columns_to_replace].replace({True: 'Yes', False: 'No'})

    # Replace values based on the condition
    columns_to_modify = ['position_1', 'position_2']
    similar_df[columns_to_modify] = similar_df[columns_to_modify].applymap(lambda x: 'Bench' if x > 11 else 'First 11')

    # rename
    similar_df.columns = ['Player ID', 'Player Name', f'{team_1} Selection', f'{team_2} Selection',
                        f'Captained by {team_1}', f'Captained by {team_2}', f'Vice-capt by {team_1}', f'Vice-capt by {team_2}']
    
    # Resetting the index
    similar_df.index += 1  # Shift the index to start from 1
    
    return similar_df

def cleanse_onlydf(df):
    """
    Format the table that shows the players that are exclusive to only 1 of the teams.
    """
    if df.empty:
        return pd.DataFrame(columns=['Player Name', 'Player ID', 'Selection', 'Captain', 'Vice-Captain'])
    
    # make a copy
    only_df = df.copy()

    # Assuming your dataframe is named 'df'
    columns_to_replace = ['is_captain', 'is_vice_captain']
    # Replace True with 'Yes' and False with 'No' in the specified columns
    only_df[columns_to_replace] = only_df[columns_to_replace].replace({True: 'Yes', False: 'No'})

    # Replace values based on the condition
    columns_to_modify = ['position']
    only_df[columns_to_modify] = only_df[columns_to_modify].applymap(lambda x: 'Bench' if x > 11 else 'First 11')

    # select columns to display
    only_df = only_df[['web_name', 'player_id', 'position','is_captain', 'is_vice_captain']]
    # rename columns
    only_df.columns = ['Player Name', 'Player ID', 'Selection', 'Captain', 'Vice-Captain']

    # Resetting the index
    only_df = only_df.reset_index(drop=True)
    only_df.index += 1  # Shift the index to start from 1

    return only_df
    

def calculate_similarity_score(df1, df2):
    # Merge dataframes on player_id
    merged = pd.merge(df1, df2, on='player_id', how='outer', suffixes=('_1', '_2'), indicator=True)
    
    similarity_scores = []
    
    for _, row in merged.iterrows():
        if row['_merge'] == 'both':
            if (row['is_captain_1'] == row['is_captain_2'] and 
                row['is_vice_captain_1'] == row['is_vice_captain_2'] and
                ((row['position_1'] < 12 and row['position_2'] < 12) or 
                 (row['position_1'] >= 12 and row['position_2'] >= 12))):
                score = 1.0
                reason = "Perfect match"
            elif (row['is_captain_1'] != row['is_captain_2'] or 
                  row['is_vice_captain_1'] != row['is_vice_captain_2']):
                score = 0.8
                reason = "Captain/Vice-captain mismatch"
            elif ((row['position_1'] < 12 and row['position_2'] >= 12) or 
                  (row['position_1'] >= 12 and row['position_2'] < 12)):
                score = 0.5
                reason = "Position threshold mismatch"
            else:
                score = 0.0
                reason = "No match"
            
            similarity_scores.append({
                'entry_name_1': row['entry_name_1'],
                'entry_name_2': row['entry_name_2'],
                'web_name_1': row['web_name_1'],
                'web_name_2': row['web_name_2'],
                'player_id': row['player_id'],
                'position_1': row['position_1'],
                'position_2': row['position_2'],
                'is_captain_1': row['is_captain_1'],
                'is_captain_2': row['is_captain_2'],
                'is_vice_captain_1': row['is_vice_captain_1'],
                'is_vice_captain_2': row['is_vice_captain_2'],
                'similarity_score': score,
                'reason': reason
            })
    
    # Create dataframe for similar and partially similar players
    similar_df = pd.DataFrame(similarity_scores)
    
    # Players only in df1
    only_df1 = merged[merged['_merge'] == 'left_only'].drop(columns=[col for col in merged.columns if col.endswith('_2')])
    only_df1 = only_df1.rename(columns={col: col.replace('_1', '') for col in only_df1.columns})
    
    # Players only in df2
    only_df2 = merged[merged['_merge'] == 'right_only'].drop(columns=[col for col in merged.columns if col.endswith('_1')])
    only_df2 = only_df2.rename(columns={col: col.replace('_2', '') for col in only_df2.columns})
    
    # Calculate overall similarity score
    total_players = len(df1)
    if similar_df.empty:
        overall_similarity = 0
    else:
        overall_similarity = (similar_df['similarity_score'].sum() / total_players) * 100

    return round(overall_similarity, 2), similar_df, only_df1, only_df2


### END OF ANALYTICAL FUNCTIONS ###