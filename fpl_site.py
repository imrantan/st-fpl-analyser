import streamlit as st
import pandas as pd
import plotly.express as px
from API_Extraction import run_api_extraction
import numpy as np  # Required for handling conditional operations

# Set page configuration as the first Streamlit command
st.set_page_config(layout="wide", initial_sidebar_state="expanded")

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["League Statistics", "Team Overview"])

# Sidebar filters
st.sidebar.header('Filters')

# Choose League
league_id = st.sidebar.text_input('League ID', placeholder="Insert digits only")

# Validate League ID
valid_league_id = league_id.isdigit()

# Load the data with caching
@st.cache_data
def fpl_data_extraction(league_id):
    LEAGUE_NAME, hist_Teams_data, Full_Selection_Data, All_Transfers, df_Transfers_IN_OUT = run_api_extraction(game_week=38, 
                                                                                                               league_id=league_id)
    return LEAGUE_NAME, hist_Teams_data, Full_Selection_Data, All_Transfers, df_Transfers_IN_OUT

# Update button
if st.sidebar.button('Update'):
    if valid_league_id:
        league_id_int = int(league_id)

        # Display a spinner while the API call is being made
        with st.spinner('Loading data...'):
            LEAGUE_NAME, hist_Teams_data, Full_Selection_Data, All_Transfers, df_Transfers_IN_OUT = fpl_data_extraction(league_id_int)

        # Store the data in session_state to persist it across interactions
        st.session_state['LEAGUE_NAME'] = LEAGUE_NAME
        st.session_state['hist_Teams_data'] = hist_Teams_data # use this when computing points and comparing points historically.
        st.session_state['Full_Selection_Data'] = Full_Selection_Data # use this when analysing an individual team.
        st.session_state['All_Transfers'] = All_Transfers
        st.session_state['df_Transfers_IN_OUT'] = df_Transfers_IN_OUT

    else:
        st.sidebar.error("Please enter a valid number for League ID.")

# Check if data is available in session_state
if 'Full_Selection_Data' in st.session_state:
    df_Full_Selection_Data = st.session_state['Full_Selection_Data']
    df_hist_Teams_data = st.session_state['hist_Teams_data']
    LEAGUE_NAME = st.session_state['LEAGUE_NAME']

    # Game Week filter
    game_weeks = sorted(df_Full_Selection_Data['game_week'].unique().astype(int))
    selected_game_week = st.sidebar.selectbox('Select Game Week', game_weeks, index=len(game_weeks)-1)

    # First Page - Team Overview
    if page == "Team Overview":
        # Set up the Streamlit app
        st.title(f'Fantasy Premier League Stats - {LEAGUE_NAME}')

        # Entry Name filter
        entry_names = sorted(df_Full_Selection_Data['entry_name'].unique())
        selected_entry_name = st.sidebar.selectbox('Select Entry Name', entry_names)

        st.header(f"{selected_entry_name} | Game Week {int(selected_game_week)}")

        # Filter the data for the selected game week and selected entry name
        df_full_select_for_gw_entryname = df_Full_Selection_Data[(df_Full_Selection_Data['game_week'] == selected_game_week) 
                                                           & (df_Full_Selection_Data['entry_name'] == selected_entry_name)]
        df_full_select_upto_gw_entryname = df_Full_Selection_Data[(df_Full_Selection_Data['game_week'] <= selected_game_week) 
                                                            & (df_Full_Selection_Data['entry_name'] == selected_entry_name)]
        
        df_hist_teams_for_gw_entryname = df_hist_Teams_data[(df_hist_Teams_data['event'] == selected_game_week) 
                                                           & (df_hist_Teams_data['entry_name'] == selected_entry_name)]
        df_hist_teams_upto_gw_entryname = df_hist_Teams_data[(df_hist_Teams_data['event'] <= selected_game_week) 
                                                            & (df_hist_Teams_data['entry_name'] == selected_entry_name)]
        

        # Display total points
        total_points_for_gameweek = int(df_hist_teams_for_gw_entryname['points'].sum())
        total_points_upto_gameweek = int(df_hist_teams_upto_gw_entryname['points'].sum())
        st.subheader(f'Total Points for the Week: {total_points_for_gameweek} | Total Cumulative Points: {total_points_upto_gameweek}')

        # Transfers made
        total_transfers_for_gameweek = int(df_hist_teams_for_gw_entryname['event_transfers'].sum())
        total_transfers_upto_gameweek = int(df_hist_teams_upto_gw_entryname['event_transfers'].sum())
        total_deduction_for_gameweek = int(df_hist_teams_for_gw_entryname['event_transfers_cost'].sum())
        total_deduction_upto_gameweek = int(df_hist_teams_upto_gw_entryname['event_transfers_cost'].sum())

        st.subheader(f'Team Statistics for Game Week {int(selected_game_week)}')
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("No. of Transfers for the Week", total_transfers_for_gameweek)
        col2.metric("Total Transfers Made", total_transfers_upto_gameweek)
        col3.metric("Point Deductions for the Week", total_deduction_for_gameweek)
        col4.metric("Total Point Deductions", total_deduction_upto_gameweek)


        # Display player information
        first_eleven = df_full_select_for_gw_entryname[df_full_select_for_gw_entryname['position']<=11]
        bench_players = df_full_select_for_gw_entryname[df_full_select_for_gw_entryname['position']>11]
        show_first_eleven_info = first_eleven[['position', 'web_name', 'name', 'plural_name_short', 'total_points', 'points_earned']]
        show_bench_players_info = bench_players[['position', 'web_name', 'name', 'plural_name_short', 'total_points', 'points_earned']]

        # Display additional statistics
        st.subheader(f'Team Selection for Game Week {int(selected_game_week)}')
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader('First Eleven')
            st.dataframe(show_first_eleven_info, hide_index=True)

        with col_b:
            st.subheader('Bench')
            st.dataframe(show_bench_players_info, hide_index=True)

        # Display additional statistics
        st.subheader(f'Team Statistics for Game Week {int(selected_game_week)}')
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Goals", int(first_eleven['goals_scored'].sum()))
        col2.metric("Total Assists", int(first_eleven['assists'].sum()))
        col3.metric("Clean Sheets", int(first_eleven['clean_sheets'].sum()))

        # Create a bar chart of points by player
        fig_1 = px.bar(show_first_eleven_info, x='web_name', y='points_earned', title='Points Earned by Player')
        st.plotly_chart(fig_1)

        # Calculate statistics up to the selected game week
        first_eleven_cumul = df_full_select_upto_gw_entryname[df_full_select_upto_gw_entryname['position']<=11]
        bench_players_cumul = df_full_select_upto_gw_entryname[df_full_select_upto_gw_entryname['position']>11]

        # Display additional statistics
        st.subheader(f'Team Statistics up to Game Week {int(selected_game_week)}')
        col4, col5, col6 = st.columns(3)
        col4.metric("Total Goals", int(first_eleven_cumul['goals_scored'].sum()))
        col5.metric("Total Assists", int(first_eleven_cumul['assists'].sum()))
        col6.metric("Clean Sheets", int(first_eleven_cumul['clean_sheets'].sum()))

        # Create a bar chart of cumulative points
        fig_2 = px.bar(first_eleven_cumul, x='web_name', y='points_earned', title='Cumulative Points Earned by Player')
        st.plotly_chart(fig_2)

        # Most captained player
        most_captained = first_eleven_cumul[first_eleven_cumul['is_captain']]['web_name'].value_counts().nlargest(5)

        # Most selected player (by web_name)
        most_selected_web = first_eleven_cumul['web_name'].value_counts().nlargest(5)

        # Most selected player (by name)
        most_selected_name = first_eleven_cumul['name'].value_counts().nlargest(5)

        # Display raw data for verification
        st.subheader('More Statistics')
        st.write("Most Captained Players:")
        st.write(most_captained)
        st.write("Most Selected Players:")
        st.write(most_selected_web)
        st.write("Most Selected Clubs:")
        st.write(most_selected_name)

    # Second Page - League Statistics
    elif page == "League Statistics":
        st.title(f'League Statistics Overview - {LEAGUE_NAME}')

        # sort and filter data for the latest game week
        overall_performance = df_hist_Teams_data[df_hist_Teams_data['event']<=selected_game_week]
               
        # sort and filter data for the latest game week
        team_performance = df_hist_Teams_data[df_hist_Teams_data['event']==selected_game_week].sort_values(by=['league_rank'])
        
        # Rank change calculation
        df_hist_Teams_data_sorted = df_hist_Teams_data.sort_values(by=['entry_name', 'event'])
        df_hist_Teams_data_sorted['previous_rank'] = df_hist_Teams_data_sorted.groupby('entry_name')['league_rank'].shift(1)
        df_hist_Teams_data_sorted['rank_change'] = df_hist_Teams_data_sorted['league_rank'] - df_hist_Teams_data_sorted['previous_rank']

        # Filter data for the current selected game week
        team_performance = df_hist_Teams_data_sorted[df_hist_Teams_data_sorted['event'] == selected_game_week].sort_values(by=['league_rank'])

        # Create a column for arrow symbols based on rank change
        team_performance['Rank Change'] = np.where(team_performance['rank_change'] < 0, '↑',
                                                   np.where(team_performance['rank_change'] > 0, '↓', '-'))

        # Add color for the arrows (green for up, red for down, grey for no change)
        team_performance['Rank Change'] = np.where(team_performance['Rank Change'] == '↑', 
                                                   '<span style="color:green">↑</span>', 
                                                   np.where(team_performance['Rank Change'] == '↓', 
                                                            '<span style="color:red">↓</span>', 
                                                            '<span style="color:grey">-</span>'))

        # Select columns to display (including Rank Change)
        team_performance = team_performance[['entry_name','points','total_points', 'bank','value','event_transfers', 
                                             'event_transfers_cost','points_on_bench', 'league_rank', 'Rank Change']]
        
        team_performance['bank'], team_performance['value'] = team_performance['bank']/10, team_performance['value']/10

        # Rename columns for readability
        team_performance.columns = ['Team','GW Points', 'Total Points', 'Bank', 'Team Value', 'No. of GW Transfers', 
                                    'Cost of Transfers', 'Points on Bench', 'Rank', 'Change']
        
        # reorder columns
        team_performance = team_performance[['Rank', 'Change', 'Team','GW Points', 'Total Points', 
                                             'Bank', 'Team Value', 'No. of GW Transfers',
                                             'Cost of Transfers', 'Points on Bench'
                                             ]]

        # Display overall league statistics (customize this as per your needs)
        total_transfers = overall_performance['event_transfers'].sum()
        team_of_the_week = team_performance.sort_values(by='GW Points', ascending=False)['Team'].iloc[0]
        highest_valued_team = team_performance.sort_values(by='Team Value', ascending=False)['Team'].iloc[0]

        # Display summary metrics for the entire league
        st.subheader(f"Overall League Performance - Game Week {selected_game_week}")
        col1, col2, col3 = st.columns(3)
        col1.metric("Team of the Week", team_of_the_week)
        col2.metric("Highest Valued Team", highest_valued_team)
        col3.metric("Total Transfers Made in the League", total_transfers)

        # Show overall performance metrics for all teams
        st.subheader("Performance by Team")

        # Convert the DataFrame to HTML
        team_performance_html = team_performance.to_html(escape=False, index=False)

        # Display the table with rank changes using st.markdown
        st.markdown(team_performance_html, unsafe_allow_html=True)

        # Line chart of team performance across game weeks
        st.subheader(f'Team Performance across Game Weeks')
        y_axis = st.selectbox('Y-axis', ['GW Points', 'Total Points', 'Team Value', 'Bank', 'No. of GW Transfers'], index=0)

        # Select columns to display (including Rank Change)
        overall_performance = overall_performance[['event', 'entry_name','points','total_points', 'bank','value','event_transfers', 
                                             'event_transfers_cost','points_on_bench', 'league_rank']]
        
        overall_performance['bank'], overall_performance['value'] = overall_performance['bank']/10, overall_performance['value']/10

        # Rename columns for readability
        overall_performance.columns = ['Event', 'Team','GW Points', 'Total Points', 'Bank', 'Team Value', 'No. of GW Transfers', 
                                       'Cost of Transfers', 'Points on Bench', 'Rank']

        chart_title = f"{y_axis.capitalize()} Earned by Teams across Game Weeks"
        fig_2 = px.line(overall_performance, 
                        x='Event', 
                        y=y_axis,
                        color='Team', 
                        title=chart_title)

        # Add circle markers to the line chart
        fig_2.update_traces(mode='lines+markers', marker=dict(symbol='circle'))

        # Update the x-axis to show only integer ticks
        fig_2.update_layout(
            xaxis=dict(
                tickmode='linear',
                tick0=1,  # Start from game week 1
                dtick=1   # Show every game week (1-week intervals)
            )
        )

        st.plotly_chart(fig_2)

else:
    st.write("Please click 'Update' to load the data.")
