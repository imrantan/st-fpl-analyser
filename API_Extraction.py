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

    # Print the timestamp when the code starts
    start_time  = datetime.datetime.now()
    print(f"Code started at: {start_time }")

    ### CONSTANTS ###

    # base url for all FPL API endpoints
    BASE_URL = 'https://fantasy.premierleague.com/api/'
                
    # league id and names
    LEAGUE_ID = int(league_id)

    # MAX Game Week
    MAX_GW = game_week
    print(f"EXTRACTING DATA UP TO GAME WEEK {MAX_GW}")

    ### Part 1 ###
    
    # 1. CREATE the dim_Teams table
    # Get information about the current league standings
    print(BASE_URL+f'leagues-classic/{LEAGUE_ID}/standings/')
    df_standings = requests.get(BASE_URL+f'leagues-classic/{LEAGUE_ID}/standings/').json()

    # get the league Name
    LEAGUE_NAME = df_standings['league']['name']
    
    # get player data from 'elements' field
    standings = df_standings['standings']

    # create teams dataframe
    standings = pd.json_normalize(standings['results'])

    # Firstly we create a dimension table to store the important information on all the teams in the league
    dim_Teams = standings[['id', 'player_name', 'entry', 'entry_name']]
    
    # 2. Create the preliminary hist_Teams_data table
    # we can proceed to loop through all the entry ids
    hist_Teams_data = pd.DataFrame() # Initialise a dataframe

    for entry in dim_Teams['entry']:
        df_history = requests.get(BASE_URL+f'entry/{entry}/history').json()
        # create teams dataframe
        historical_standings = pd.json_normalize(df_history['current'])
        # add a column for the entry id
        historical_standings['entry'] = entry
        hist_Teams_data = pd.concat([hist_Teams_data, historical_standings])
        
    # 3. Merge dim_Teams and hist_Teams_data. We can overwrite the hist_Teams_data
    # perform left join so we can get the team names
    hist_Teams_data = pd.merge(left=dim_Teams,
                            right=hist_Teams_data,
                            left_on='entry',
                            right_on='entry',
                            how='left')
    
    # 4. Sorting within each 'event' group by 'total_points' in descending order and assigning rank
    hist_Teams_data['league_rank'] = hist_Teams_data.groupby('event')['total_points'].rank(method='dense',
                                                                                        ascending=False).astype(int)


    ### PART 2 ###
    
    ### Part 1: Create the All_TeamSelections DataFrame ###

    # Now lets write a script to get the list of team selections for every week

    All_TeamSelections = pd.DataFrame() # initialise a dataframe to store data for all gameweeks

    # 1. loop through all the weeks until the max week
    for GW in range(1,MAX_GW+1):

        # 2. loop through all the teams for that week
        for entry in hist_Teams_data[hist_Teams_data['event']==GW]['entry']:

            # 1. load the data
            team_picks = requests.get(BASE_URL+f'entry/{entry}/event/{GW}/picks/').json()

            #2. Get the team selection table
            team_selection = pd.json_normalize(team_picks['picks'])
            # add 2 colums
            team_selection['entry'] = entry
            team_selection['event'] = GW

            # get the automatic subs table
            auto_subs = pd.json_normalize(team_picks['automatic_subs'])

            # check if there are no subs.
            if auto_subs.empty:
                # If empty, create a new DataFrame with specified columns
                specified_columns = ['entry', 'element_in', 'element_out', 'event']  # Replace these column names with your specified columns
                auto_subs = pd.DataFrame(columns=specified_columns)

            # we merge to flag that the player was auto subbed in for who or auto subbed out for who
            # first Join is to pull element_out column
            team_selection = pd.merge(left=team_selection,
                                    right=auto_subs[['element_in', 'element_out']],
                                    left_on='element',
                                    right_on='element_in',
                                    how='left')

            team_selection = team_selection.drop('element_in', axis=1) # drop the element_in column

            # Second Join is to pull element_in column
            team_selection = pd.merge(left=team_selection,
                                    right=auto_subs[['element_in', 'element_out']],
                                    left_on='element',
                                    right_on='element_out',
                                    how='left')

            team_selection = team_selection.drop('element_out_y', axis=1) # drop the element_out_y column
            team_selection.rename(columns={"element_out_x": "element_out"}, inplace=True)

            # 4. Append the temp_df to the 
            All_TeamSelections = pd.concat([All_TeamSelections, team_selection])


        ### END OF PART 1 ###

        # We now need to obtain the following information on the players selected:
        # 1. Player name
        # 2. Player info (age, club, country etc.)
        # 3. Points earned for the corresponding week

        ### PART 2: Create the All_GW_data dataframe ###

        # let's try and pull a dataframe of all the GW data

        All_GW_data = pd.DataFrame() # initialise a dataframe to store data for all gameweeks

        # 1. loop through all the weeks until the max week
        for GW in range(1,MAX_GW+1):
            game_week = requests.get(BASE_URL+f'event/{GW}/live/').json()
            elements = game_week['elements']

            temp_df = pd.DataFrame() # initialise an empty dataframe for each week

            # 2. Loop through all the players in the elements list
            for player in elements:

                # 1. take the stats out for the player
                temp_player = pd.json_normalize(player['stats'])

                # 2. get the id of the player
                temp_player['player_id'] = player['id']

                # 3. append to the empty dataframe
                temp_df = pd.concat([temp_df, temp_player])

            # 3. Add a column for the game week
            temp_df['game_week'] = GW

            # 4. Append the temp_df to the 
            All_GW_data = pd.concat([All_GW_data, temp_df])

        ### END OF PART 2 ###

        # Now let's retrieve the other player informations.

        ### PART 3: Rertrieve the rest of the player's information ###

        #  https://fantasy.premierleague.com/api/bootstrap-static/
        # load data on the main_info
        main_info = requests.get(BASE_URL+f'bootstrap-static/').json()

        # get dataframe of information on player
        main_player_info = pd.json_normalize(main_info['elements'])
        # the stats change week on week. I just want to keep the crucial information on the player.
        important_columns = ['id',
                            'element_type',
                            'first_name',
                            'second_name',
                            'web_name',
                            'team',
                            'team_code'
                            ]
        main_player_info = main_player_info[important_columns]


        # get information on all the teams
        team_info = pd.json_normalize(main_info['teams'])
        # keep important columns
        important_columns = ['code',
                            'name',
                            'short_name',
                            'pulse_id'
                            ]
        team_info = team_info[important_columns]

        # get information on all the teams
        element_types_info = pd.json_normalize(main_info['element_types'])
        # keep important columns
        important_columns = ['id',
                            'plural_name',
                            'plural_name_short',
                            'singular_name'
                            ]
        element_types_info = element_types_info[important_columns]

        # Perform Joins to obtain the data on the players

        # 1. start with getting the data on clubs
        player_data = pd.merge(left=team_info,
                            right=main_player_info,
                            left_on='code',
                            right_on='team_code',
                            how='left',
                            suffixes=('_team', '_player'))

        # 2. Get position
        player_data = pd.merge(left=player_data,
                            right=element_types_info,
                            left_on='element_type',
                            right_on='id',
                            how='left',
                            suffixes=('_player', '_position'))
        

        ### END OF PART 3 ###

        # Now we can perform left join to combine the player stats per week with the player information

        ### PART 4: Merge all tables together ###

        # perform left join
        All_Player_GW_data = pd.merge(left=player_data,
                            right=All_GW_data,
                            left_on='id_player',
                            right_on='player_id',
                            how='left',
                            suffixes=('_PLAYER', '_GW'))

        # Now we have our 2 main tables:
        # 1. All_TeamSelections - to get the players which the teams selected for the week
        # 2. All_Player_GW_data - to get the number of points the player gained for the week

        # We can proceed to perform a join to combine these 2 tables.

        # print(len(All_TeamSelections))
        # perform left join
        Full_Selection_Data = pd.merge(left=All_TeamSelections,
                            right=All_Player_GW_data,
                            left_on=['event', 'element'],
                            right_on=['game_week', 'player_id'],
                            how='left',
                            suffixes=('_TeamSelections', '_PlayerGW'))
        # print(len(Full_Selection_Data))

        # Now let's bring in the information of the different teams in the league
        Full_Selection_Data = pd.merge(left=dim_Teams,
                            right=Full_Selection_Data,
                            left_on='entry',
                            right_on='entry',
                            how='left',
                            suffixes=('_Team', '_Selection'))

        # Last step create a column for points earned by player
        Full_Selection_Data['points_earned'] = Full_Selection_Data['multiplier']*Full_Selection_Data['total_points']

        ### END OF PART 4 ###


    ### PART 3 ###
    
    total_errors = 0
    
    # 1. loop through all the weeks until the max week
    for GW in range(1,MAX_GW+1):
        print(f'\033[1mChecking for Game Week {GW} now...\033[0m')
        error_counter = 0
        # 2. loop through all the teams for that week
        for entry in dim_Teams['entry']:
            query_string = f"entry == {entry} and event == {GW}"
            player_name = dim_Teams[dim_Teams['entry']==entry]['player_name'].iloc[0]
            hist_Teams_data_result = hist_Teams_data.query(query_string)
            Full_Selection_Data_result = Full_Selection_Data.query(query_string)
            
            # Some players join midseason so the data on points is not available
            if hist_Teams_data_result.empty:
                hist_Teams_data_points = 0
            else:
                hist_Teams_data_points = hist_Teams_data_result['points'].iloc[0]
                
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


    ### PART 5 ###
    All_Transfers  = pd.DataFrame() # initialise dataframe

    # 2. loop through all the teams for that week
    for entry in dim_Teams['entry']:
        df_transfers = requests.get(BASE_URL+f'entry/{entry}/transfers/').json()
        df_transfers = pd.json_normalize(df_transfers)

        All_Transfers = pd.concat([All_Transfers,df_transfers])
        
    # 1. First Join to retrieve the team information
    All_Transfers = pd.merge(left=All_Transfers,
                            right=dim_Teams,
                            left_on='entry',
                            right_on='entry',
                            how='left',
                            suffixes=('_Team', '_Transfer'))

    important_columns = ['name', 'id_player', 'first_name', 'second_name', 'web_name', 'singular_name']
    player_data = player_data[important_columns]

    # 2. Retrieve the element_in Player info
    All_Transfers = pd.merge(left=All_Transfers,
                                            right=player_data,
                                            left_on='element_in',
                                            right_on='id_player',
                                            how='left',
                                            suffixes=('_Team', '_PlayerIn'))

    # 3. Retrieve the element_out Player info
    All_Transfers = pd.merge(left=All_Transfers,
                                            right=player_data,
                                            left_on='element_out',
                                            right_on='id_player',
                                            how='left',
                                            suffixes=('_PlayerIn', '_PlayerOut'))

    # ensure that only the latest gameweek gets transferred
    All_Transfers = All_Transfers[All_Transfers['event']<=MAX_GW]
    
    # clean the cost. divide by 10 to get the same cost displayed in the FPL site
    All_Transfers['element_in_cost'] = All_Transfers['element_in_cost']/10
    All_Transfers['element_out_cost'] = All_Transfers['element_out_cost']/10
    
    # create separate date and time columns
    All_Transfers['time'] = pd.to_datetime(All_Transfers['time'])  # Convert to datetime format
    
    # Convert UTC to Singapore Time (SGT)
    sgt_timezone = pytz.timezone('Asia/Singapore')
    All_Transfers['time_SG'] = All_Transfers['time'].dt.tz_convert(sgt_timezone)
    
    # Splitting datetime column into date and time columns
    All_Transfers['date_clean'] = All_Transfers['time_SG'].dt.date
    All_Transfers['time_clean'] = All_Transfers['time_SG'].dt.time
    
    
    # 26th Dec 2023. I decided to include league rank in the data set. to see what interesting insights we can achieve.
    # Take only important column
    important_columns = ['entry', 'event', 'league_rank']
    hist_Teams_data_lite = hist_Teams_data[important_columns]
    All_Transfers = pd.merge(left=All_Transfers,
                            right=hist_Teams_data_lite,
                            left_on=['event','entry'],
                            right_on=['event','entry'],
                            how='left')
    
    # Assign a Transfer ID. Useful later in tableau if we want to do some relationships.
    All_Transfers.reset_index(inplace=True) # reset index
    All_Transfers['Transfer_ID'] = All_Transfers.index


    ### PART 6 ###

    # Identify columns before the Loop
    common_columns = ['entry', 'event',
                    'league_rank', 'time',
                    'id', 'player_name',
                    'entry_name','time_SG',
                    'date_clean', 'time_clean', 'Transfer_ID']

    columns_for_PlayerIn = ['element_in', 'element_in_cost',
                            'name_PlayerIn', 'id_player_PlayerIn',
                            'first_name_PlayerIn', 'second_name_PlayerIn',
                            'web_name_PlayerIn', 'singular_name_PlayerIn']

    columns_for_PlayerOut = ['element_out', 'element_out_cost',
                            'name_PlayerOut', 'id_player_PlayerOut',
                            'first_name_PlayerOut', 'second_name_PlayerOut',
                            'web_name_PlayerOut', 'singular_name_PlayerOut']

    # standardise new columns
    standardised_columns = ['element', 'element_cost',
                            'name', 'id_player',
                            'first_name', 'second_name',
                            'web_name', 'singular_name']
    
    
    # 1. split the columns for PlayerIn and PLayerOut
    # 2. then append the tables together

    # Split and Create 2 new dataframes
    df_Transfer_Ins, df_Transfer_Outs = All_Transfers[common_columns+columns_for_PlayerIn], All_Transfers[common_columns+columns_for_PlayerOut]

    # standardise and rename columns. and add 1 new column
    df_Transfer_Ins.columns, df_Transfer_Outs.columns = common_columns+standardised_columns, common_columns+standardised_columns

    df_Transfer_Ins['Direction'] = 'In'
    df_Transfer_Outs['Direction'] = 'Out'

    # now we append
    df_Transfers_IN_OUT = pd.concat([df_Transfer_Ins, df_Transfer_Outs])

    # Record the end time
    end_time = datetime.datetime.now()
    print(f"Code ended at: {end_time}")

    # Calculate the elapsed time
    elapsed_time = end_time - start_time

    # Convert elapsed_time to hours:minutes:seconds format
    hours, remainder = divmod(elapsed_time.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    # Format the elapsed time
    elapsed_time_formatted = f"{hours:02}:{minutes:02}:{seconds:02}"

    print(f"Elapsed time: {elapsed_time_formatted}")


    return LEAGUE_NAME, hist_Teams_data, Full_Selection_Data, All_Transfers, df_Transfers_IN_OUT