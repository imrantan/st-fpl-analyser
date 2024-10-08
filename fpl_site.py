import streamlit as st
import pandas as pd
import plotly.express as px
from fpl_functions import run_api_extraction, calculate_similarity_score, cleanse_similar_df, cleanse_onlydf
import numpy as np  # Required for handling conditional operations
import random

# Your Streamlit app code here

# Set page configuration as the first Streamlit command
st.set_page_config(layout="wide", initial_sidebar_state="collapsed", page_title="The FPL Analyser")

# Custom CSS for styling
st.markdown("""
    <style>
    .big-font {
        font-size:50px !important;
        color: #00ff87;
        font-weight: bold;
    }
    .medium-font {
        font-size:32px !important;
        color: #00ff87;
        font-weight: bold;
    }
    .subheader {
        font-size:25px;
        color: #ffffff;
    }
    .creator {
        font-size:14px;
        color: #cccccc;
        font-style: italic;
    }
            
    </style>
    """, unsafe_allow_html=True)

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Overall League", 
                                  "Individual Team Overview", 
                                  "Similarity Analyser", 
                                  "Transfer Statistics",
                                  "Home"])

# Sidebar filters
st.sidebar.header('Filters')

# Choose League
league_id = st.sidebar.text_input('League ID', placeholder="Insert digits only")
st.sidebar.write('Popular League IDs:')
st.sidebar.write('TakGooner - 1033088')
st.sidebar.write('IHG 24/25 - 723575')
st.sidebar.write('Potato Farm - 2306035')

# Validate League ID
valid_league_id = league_id.isdigit()

# Load the data with caching
@st.cache_data(ttl=14400) # every 4hrs clear cache
def fpl_data_extraction(league_id):
    LEAGUE_NAME, start_event, hist_Teams_data, Full_Selection_Data, All_Transfers, df_Transfers_IN_OUT = run_api_extraction(game_week=38, 
                                                                                                            league_id=league_id)
    return LEAGUE_NAME, start_event, hist_Teams_data, Full_Selection_Data, All_Transfers, df_Transfers_IN_OUT

def home():
    """
    This function creates the homepage.
    """
    # Header
    st.markdown('<p class="big-font">The FPL Analyser \u26BD</p>', unsafe_allow_html=True)
    st.markdown('<p class="subheader">Dive deep into your fantasy premier league\'s performance \U0001F4CA</p>', unsafe_allow_html=True)
    
    # Graphic - TBD
    # st.image("https://via.placeholder.com/800x400.png?text=FPL+Analysis+Dashboard", use_column_width=True)
    
    # Description
    st.write("""
    Welcome to the FPL Analyser! This tool allows you to:
    
    - Analyze overall fantasy premier league performance
    - Dive into individual team statistics
    - Track player selections and captain choices
    - Monitor transfers and their impact
    - And try out the NEW Similarity Analyser!
    
    To get started, enter your league ID in the sidebar and click 'Update'.
    """)
    
    # Creator credit
    st.markdown('<p class="creator">Created by https://github.com/imrantan</p>', unsafe_allow_html=True)

    # add some spacings
    st.markdown('', unsafe_allow_html=True)
    st.markdown('', unsafe_allow_html=True)
    st.markdown('', unsafe_allow_html=True)

    # Add the disclaimer at the bottom with custom styling
    st.markdown(
        """
        <div style="width: 100%; text-align: left; font-size: small; font-style: italic;">
            Disclaimer: This project is not affiliated with or endorsed by the official Fantasy Premier League or Premier League. 
            It is a fan-made tool intended for personal use and analysis. Please use responsibly and in accordance with the Fantasy Premier League's terms of service.
        </div>
        """,
        unsafe_allow_html=True
    )

# Update button
if st.sidebar.button('Update'):
    if valid_league_id:
        league_id_int = int(league_id)

        # Display a spinner while the API call is being made
        with st.spinner('Loading data. This might take awhile...'):
            LEAGUE_NAME, start_event, hist_Teams_data, Full_Selection_Data, All_Transfers, df_Transfers_IN_OUT = fpl_data_extraction(league_id_int)

        # Store the data in session_state to persist it across interactions
        st.session_state['LEAGUE_NAME'] = LEAGUE_NAME
        st.session_state['start_event'] = start_event
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
    df_Transfers_IN_OUT = st.session_state['df_Transfers_IN_OUT']
    df_All_Transfers = st.session_state['All_Transfers']
    LEAGUE_NAME = st.session_state['LEAGUE_NAME']
    start_event = st.session_state['start_event']

    # Game Week filter
    game_weeks = sorted(df_Full_Selection_Data['game_week'].unique().astype(int))
    selected_game_week = st.sidebar.selectbox('Select Game Week', game_weeks, index=len(game_weeks)-1)

    barchart_dragmode = False # pre-set to control if the user can drag and pan the charts
    # Function to create horizontal bar charts using plotly
    def plot_horizontal_bar(data, title, x_label, y_label):
        fig = px.bar(
            data_frame=data,
            x=data.values, 
            y=data.index, 
            orientation='h',  # Horizontal bar chart
            title=title,
            labels={  # Customize axis labels
                "x": x_label,
                "y": y_label
            }   
        )
        # Update the color of the bars
        fig.update_traces(marker_color='#00ff87')
        # Update layout to sort bars in descending order
        fig.update_layout(yaxis={'categoryorder': 'total ascending'},
                          dragmode=barchart_dragmode,)
        return fig

    # First Page - Team Overview
    if page == "Home":
        home() # show homepage

    elif page == "Individual Team Overview":

        # Entry Name filter
        entry_names = sorted(df_Full_Selection_Data['entry_name'].unique())
        selected_entry_name = st.sidebar.selectbox('Select Entry Name', entry_names)

        team_performance = df_hist_Teams_data[(df_hist_Teams_data['event']==selected_game_week) & (df_hist_Teams_data['entry_name']==selected_entry_name)]
        
        team_position = team_performance['league_rank'].iloc[0]

        # Set up the Streamlit app
        st.markdown(f'<p class="big-font">FPL Team Stats - {selected_entry_name}</p>', unsafe_allow_html=True)

        st.header(f"{LEAGUE_NAME} - Rank {team_position} | Game Week {int(selected_game_week)}")

        # Filter the data for the selected game week and selected entry name
        df_full_select_for_gw_entryname = df_Full_Selection_Data[(df_Full_Selection_Data['game_week'] == selected_game_week) 
                                                        & (df_Full_Selection_Data['entry_name'] == selected_entry_name)]
        df_full_select_upto_gw_entryname = df_Full_Selection_Data[(df_Full_Selection_Data['game_week'] <= selected_game_week) 
                                                            & (df_Full_Selection_Data['entry_name'] == selected_entry_name)]
        
        df_hist_teams_for_gw_entryname = df_hist_Teams_data[(df_hist_Teams_data['event'] == selected_game_week) 
                                                        & (df_hist_Teams_data['entry_name'] == selected_entry_name)]
        df_hist_teams_upto_gw_entryname = df_hist_Teams_data[(df_hist_Teams_data['event'] <= selected_game_week) 
                                                            & (df_hist_Teams_data['entry_name'] == selected_entry_name)]
        
        # retrieve prior week data
        df_hist_teams_for_prior_gw_entryname = df_hist_Teams_data[(df_hist_Teams_data['event'] == selected_game_week-1) 
                                                        & (df_hist_Teams_data['entry_name'] == selected_entry_name)]
        

        # Display total points
        total_points_for_gameweek = int(df_hist_teams_for_gw_entryname['points'].sum())

        if len(df_hist_teams_for_prior_gw_entryname) != 0:
            total_points_for_prior_gameweek = int(df_hist_teams_for_prior_gw_entryname['points'].sum())
        else:
            total_points_for_prior_gameweek = 0

        # calculate week on week change %
        points_change = total_points_for_gameweek - total_points_for_prior_gameweek

        if total_points_for_prior_gameweek==0:
            points_change_percentage = 'N.A.'
        else:
            points_change_percentage = (points_change/total_points_for_prior_gameweek)*100
            points_change_percentage = f'{points_change_percentage:.1f}%'

        total_points_upto_gameweek = int(df_hist_teams_upto_gw_entryname['points'].sum())

        st.subheader(f'Overall Results for Game Week {int(selected_game_week)}')

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Points for the Week", total_points_for_gameweek)
        col2.metric("Total Cumulative Points", total_points_upto_gameweek)
        col3.metric("Current Week vs Prior Week Points", points_change)
        col4.metric("Current Week vs Prior Week % Change", points_change_percentage)
        
        # Transfers made
        total_transfers_for_gameweek = int(df_hist_teams_for_gw_entryname['event_transfers'].sum())
        total_transfers_upto_gameweek = int(df_hist_teams_upto_gw_entryname['event_transfers'].sum())
        total_deduction_for_gameweek = int(df_hist_teams_for_gw_entryname['event_transfers_cost'].sum())
        total_deduction_upto_gameweek = int(df_hist_teams_upto_gw_entryname['event_transfers_cost'].sum())

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("No. of Transfers for the Week", total_transfers_for_gameweek)
        col2.metric("Total Transfers Made", total_transfers_upto_gameweek)
        col3.metric("Point Deductions for the Week", total_deduction_for_gameweek)
        col4.metric("Total Point Deductions", total_deduction_upto_gameweek)

        # Add a horizontal dividing line
        st.markdown("---")

        # Display player information
        first_eleven = df_full_select_for_gw_entryname[df_full_select_for_gw_entryname['position']<=11]
        bench_players = df_full_select_for_gw_entryname[df_full_select_for_gw_entryname['position']>11]
        show_first_eleven_info = first_eleven[['position', 'web_name', 'name', 
                                            'plural_name_short', 'total_points', 'points_earned']]
        show_bench_players_info = bench_players[['position', 'web_name', 'name', 
                                                'plural_name_short', 'total_points', 'points_earned']]
        
        # first 11 + bench
        full_team_info = df_full_select_for_gw_entryname[['position', 'web_name', 'name', 'plural_name_short', 
                                                          'total_points', 'points_earned']]
        full_team_info.columns = ['No.', 'Name', 'Club', 'Position', 'GW Points', 'Points Earned'] 
        
        # show the transfers made
        transfers_for_the_week = df_Transfers_IN_OUT[(df_Transfers_IN_OUT['entry_name']==selected_entry_name) 
                                                    & (df_Transfers_IN_OUT['event']==selected_game_week)]
        
        transfers_for_the_week = transfers_for_the_week[['date_clean','time_clean','Transfer_ID', 'element_cost', 
                                                        'name', 'web_name', 'singular_name', 'Direction', 'id_player', 'total_points']].sort_values(by='Transfer_ID')

        # Display additional statistics
        st.subheader(f'Team Selection for Game Week {int(selected_game_week)}')
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader('First Eleven')
            show_first_eleven_info.columns = ['No.', 'Name', 'Club', 'Position', 'GW Points', 'Points Earned']
            st.dataframe(show_first_eleven_info, hide_index=True, use_container_width=True, height=420)

        with col_b:
            st.subheader('Bench')
            show_bench_players_info.columns = ['No.', 'Name', 'Club', 'Position', 'GW Points', 'Points Earned']
            st.dataframe(show_bench_players_info, hide_index=True, use_container_width=True)

            st.subheader('Transfers')
            transfers_for_the_week.columns = ['Date', 'Time', 'Transfer ID', 'Cost', 'Club', 
                                            'Name', 'Position', 'Direction', 'Player ID', 'GW Points']
            st.dataframe(transfers_for_the_week, hide_index=True, use_container_width=True)

        # Add a horizontal dividing line
        st.markdown("---")

        # sort and filter data for the latest game week
        overall_performance = df_hist_Teams_data[df_hist_Teams_data['event']<=selected_game_week]

        # Select columns to display (including Rank Change)
        overall_performance = overall_performance[['event', 'entry_name','points','total_points', 'bank','value','event_transfers', 
                                            'event_transfers_cost','points_on_bench', 'league_rank']]
        
        overall_performance['bank'], overall_performance['value'] = overall_performance['bank']/10, overall_performance['value']/10

        # Rename columns for readability
        overall_performance.columns = ['Game Week', 'Team','GW Points', 'Total Points', 'Bank', 'Team Value', 'No. of GW Transfers', 
                                    'Cost of Transfers', 'Points on Bench', 'Rank']

        st.subheader(f'Performance Comparison')
        y_axis = st.selectbox('Y-axis', ['GW Points', 'Total Points', 'Rank', 
                                         'Team Value', 'Bank', 'No. of GW Transfers'], index=0)

        chart_title = f"{y_axis} across Game Weeks"
        fig_2 = px.line(overall_performance,
                        x='Game Week', 
                        y=y_axis,
                        color='Team', 
                        title=chart_title)
        
        # Highlight the selected entry by making others faint
        for trace in fig_2.data:
            if trace.name == selected_entry_name:
                trace.update(line=dict(width=3, color='#00ff87'), opacity=0.8)  # Highlight selected team with thicker line
            else:
                trace.update(line=dict(width=1, color='lightgray'), opacity=0.5)  # Faint the other lines

        # Add circle markers to the line chart
        fig_2.update_traces(mode='lines+markers', marker=dict(symbol='circle'))

        # Update y-axis layout conditionally based on the selected y-axis value
        yaxis_config = {}

        # Reverse the y-axis if 'Rank' is selected
        if y_axis == 'Rank':
             yaxis_config = {
                'tickmode': 'linear',
                'dtick': 1,  # Show ticks at every integer
                'autorange': 'reversed'  # Reverse the y-axis for 'Rank'
            }

        # Make the chart static by disabling hover, zoom, and pan
        fig_2.update_layout(
            yaxis=yaxis_config,  # Apply y-axis configuration if needed
            xaxis=dict(
                tickmode='linear',
                tick0=1,  # Start from game week 1
                dtick=1   # Show every game week (1-week intervals)
            ),
            showlegend=False,
            dragmode=False,   # Disable drag (zoom/pan)
        )

        st.plotly_chart(fig_2)

        # Add a horizontal dividing line
        st.markdown("---")

        st.subheader(f'Team Statistics for Game Week {int(selected_game_week)}')

        # Display additional statistics
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Goals", int(first_eleven['goals_scored'].sum()))
        col2.metric("Total Assists", int(first_eleven['assists'].sum()))
        col3.metric("Clean Sheets", int(first_eleven['clean_sheets'].sum()))

        # Create a slider for selecting TOP N
        col1, col2, col3 = st.columns(3)
        with col1:
            top_n = st.slider('Select TOP N players:', 1, 20, 10)  # Default to 5

        # Create a bar chart of points by player
        top_players = full_team_info.nlargest(top_n, 'Points Earned')
        fig_1 = px.bar(top_players, x='Name', y='Points Earned', title=f'Top {top_n} Players By Points Earned')
        # Update the color of the bars
        fig_1.update_traces(marker_color='#00ff87')
        fig_1.update_layout(xaxis_title=None) # remove x-axis title
        # Update layout to sort bars in descending order
        fig_1.update_layout(xaxis={'categoryorder': 'total descending'}, dragmode=barchart_dragmode)
        st.plotly_chart(fig_1)


        # Calculate statistics up to the selected game week
        first_eleven_cumul = df_full_select_upto_gw_entryname[df_full_select_upto_gw_entryname['position']<=11]
        bench_players_cumul = df_full_select_upto_gw_entryname[df_full_select_upto_gw_entryname['position']>11]

        # full team
        full_team_cumul = df_full_select_upto_gw_entryname[['position', 'web_name', 'name', 'plural_name_short', 
                                                            'total_points', 'points_earned', 'is_captain']]
        full_team_cumul.columns = ['No.', 'Name', 'Club', 'Position', 'GW Points', 'Points Earned', 'Captain']

        # Display additional statistics
        st.subheader(f'Team Statistics up to Game Week {int(selected_game_week)}')
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Goals", int(first_eleven_cumul['goals_scored'].sum()))
        col2.metric("Total Assists", int(first_eleven_cumul['assists'].sum()))
        col3.metric("Clean Sheets", int(first_eleven_cumul['clean_sheets'].sum()))

        # Ranks all the players ever selected by their points contribution to the team
        # Filter DataFrame for TOP N players
        # Group by 'Name' and aggregate by summing the 'Points Earned' for each player
        agg_team_cumul = full_team_cumul.groupby('Name', as_index=False).agg({'Points Earned': 'sum'})
        top_players = agg_team_cumul.nlargest(top_n, 'Points Earned')
        fig_2 = px.bar(top_players, x='Name', y='Points Earned', title=f'Top {top_n} Players By Cumulative Points Earned')
        # Update the color of the bars
        fig_2.update_traces(marker_color='#00ff87')
        fig_2.update_layout(xaxis_title=None) # remove x-axis title
        fig_2.update_layout(xaxis={'categoryorder': 'total descending'}, dragmode=barchart_dragmode)
        st.plotly_chart(fig_2)

        # Analyse the first eleven only. players that made it to the game week team.
        first_eleven_cumul = first_eleven_cumul[['position', 'web_name', 'name', 
                                                'plural_name_short', 'total_points', 'points_earned', 'is_captain']]
        first_eleven_cumul.columns = ['No.', 'Name', 'Club', 'Position', 'GW Points', 'Points Earned', 'Captain']
        
        # Most captained players
        most_captained = first_eleven_cumul[first_eleven_cumul['Captain']]['Name'].value_counts().nlargest(5)

        # Most selected player (by web_name)
        most_selected_web = first_eleven_cumul['Name'].value_counts().nlargest(5)

        # Most selected player (by name)
        most_selected_name = first_eleven_cumul['Club'].value_counts().nlargest(5)

        # Subheader for more statistics
        st.subheader('More Statistics')

        bar1, bar2, bar3 = st.columns(3)

        # Plot Most Captained Players
        with bar1:
            fig1 = plot_horizontal_bar(most_captained, "Most Captained Players", "Count", "Player")
            st.plotly_chart(fig1)

        # Plot Most Selected Players by Web Name
        with bar2:
            fig2 = plot_horizontal_bar(most_selected_web, "Most Selected Players", "Count", "Player")
            st.plotly_chart(fig2)

        # Plot Most Selected Players by Name
        with bar3:
            fig3 = plot_horizontal_bar(most_selected_name, "Most Selected Clubs", "Count", "Club")
            st.plotly_chart(fig3)
        
    elif page == "Overall League":
        st.markdown(f'<p class="big-font">League Statistics Overview - {LEAGUE_NAME}</p>', unsafe_allow_html=True)

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
        team_performance['Rank Change'] = np.where(team_performance['rank_change'] < 0, '▲',
                                                np.where(team_performance['rank_change'] > 0, '▼', '–'))

        # Add color for the arrows (green for up, red for down, grey for no change)
        team_performance['Rank Change'] = np.where(team_performance['Rank Change'] == '▲', 
                                                '<span style="color:green">▲</span>', 
                                                np.where(team_performance['Rank Change'] == '▼', 
                                                            '<span style="color:red">▼</span>', 
                                                            '<span style="color:grey">–</span>'))

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

        # Add a horizontal dividing line
        st.markdown("---")

        # Line chart of team performance across game weeks
        st.subheader(f'Teams Performance across Game Weeks')
        

        # Select columns to display (including Rank Change)
        overall_performance = overall_performance[['event', 'entry_name','points','total_points', 'bank','value','event_transfers', 
                                            'event_transfers_cost','points_on_bench', 'league_rank']]
        
        overall_performance['bank'], overall_performance['value'] = overall_performance['bank']/10, overall_performance['value']/10

        # Rename columns for readability
        overall_performance.columns = ['Game Week', 'Team','GW Points', 'Total Points', 'Bank', 'Team Value', 'No. of GW Transfers', 
                                    'Cost of Transfers', 'Points on Bench', 'Rank']
        
        y_axis = st.selectbox('Y-axis', ['GW Points', 'Total Points', 'Rank', 'Team Value', 'Bank', 'No. of GW Transfers'], index=0)

        chart_title = f"{y_axis} by Teams across Game Weeks"
        fig_2 = px.line(overall_performance, 
                        x='Game Week', 
                        y=y_axis,
                        color='Team', 
                        title=chart_title)

        # Add circle markers to the line chart
        fig_2.update_traces(mode='lines+markers', marker=dict(symbol='circle'))

        # Update y-axis layout conditionally based on the selected y-axis value
        yaxis_config = {}

        # Reverse the y-axis if 'Rank' is selected
        if y_axis == 'Rank':
             yaxis_config = {
                'tickmode': 'linear',
                'dtick': 1,  # Show ticks at every integer
                'autorange': 'reversed'  # Reverse the y-axis for 'Rank'
            }

        # Update the x-axis to show only integer ticks
        fig_2.update_layout(
            yaxis=yaxis_config,
            xaxis=dict(
                tickmode='linear',
                tick0=1,  # Start from game week 1
                dtick=1   # Show every game week (1-week intervals)
            )
        )

        st.plotly_chart(fig_2)

        # Filter the data for the selected game week and selected entry name
        df_full_select_for_gw = df_Full_Selection_Data[(df_Full_Selection_Data['game_week'] == selected_game_week)]
                                                        
        df_full_select_upto_gw = df_Full_Selection_Data[(df_Full_Selection_Data['game_week'] <= selected_game_week)]                      
        
        df_hist_teams_for_gw = df_hist_Teams_data[(df_hist_Teams_data['event'] == selected_game_week)] 
                                                        
        df_hist_teams_upto_gw = df_hist_Teams_data[(df_hist_Teams_data['event'] <= selected_game_week)]

        # Calculate statistics up to the selected game week
        first_eleven_cumul = df_full_select_upto_gw[df_full_select_upto_gw['position']<=11]
        # bench_players_cumul = df_full_select_upto_gw[df_full_select_upto_gw['position']>11]

        first_eleven_cumul = first_eleven_cumul[['position', 'web_name', 'name', 
                                                'plural_name_short', 'total_points', 'points_earned', 'is_captain']]
        first_eleven_cumul.columns = ['No.', 'Name', 'Club', 'Position', 'GW Points', 'Points Earned', 'Captain']

        # show some barcharts metrics across all the teams in the league
        # Most captained players
        most_captained = first_eleven_cumul[first_eleven_cumul['Captain']]['Name'].value_counts().nlargest(5)

        # Most selected player (by web_name)
        most_selected_web = first_eleven_cumul['Name'].value_counts().nlargest(5)

        # Most selected Club
        most_selected_name = first_eleven_cumul['Club'].value_counts().nlargest(5)

        # Subheader for more statistics
        st.subheader(f'League Statistics up to GW{selected_game_week}')

        bar1, bar2, bar3 = st.columns(3)

        # Plot Most Captained Players
        with bar1:
            fig1 = plot_horizontal_bar(most_captained, "Most Captained Players", "Count", "Player")
            st.plotly_chart(fig1)

        # Plot Most Selected Players by Web Name
        with bar2:
            fig2 = plot_horizontal_bar(most_selected_web, "Most Selected Players", "Count", "Player")
            st.plotly_chart(fig2)

        # Plot Most Selected Players by Name
        with bar3:
            fig3 = plot_horizontal_bar(most_selected_name, "Most Selected Clubs", "Count", "Club")
            st.plotly_chart(fig3)


        # For the Game week 
        # Calculate statistics up to the selected game week
        first_eleven = df_full_select_for_gw[df_full_select_for_gw['position']<=11]

        first_eleven = first_eleven[['position', 'web_name', 'name', 
                                                'plural_name_short', 'total_points', 'points_earned', 'is_captain']]
        first_eleven.columns = ['No.', 'Name', 'Club', 'Position', 'GW Points', 'Points Earned', 'Captain']

        # show some barcharts metrics across all the teams in the league
        # Most captained players
        most_captained = first_eleven[first_eleven['Captain']]['Name'].value_counts().nlargest(5)

        # Most selected player (by web_name)
        most_selected_web = first_eleven['Name'].value_counts().nlargest(5)

        # Most selected Club
        most_selected_name = first_eleven['Club'].value_counts().nlargest(5)

        # Subheader for more statistics
        st.subheader(f'League Statistics for the GW{selected_game_week}')

        bar1, bar2, bar3 = st.columns(3)

        # Plot Most Captained Players
        with bar1:
            fig1 = plot_horizontal_bar(most_captained, "Most Captained Players", "Count", "Player")
            st.plotly_chart(fig1)

        # Plot Most Selected Players by Web Name
        with bar2:
            fig2 = plot_horizontal_bar(most_selected_web, "Most Selected Players", "Count", "Player")
            st.plotly_chart(fig2)

        # Plot Most Selected Players by Name
        with bar3:
            fig3 = plot_horizontal_bar(most_selected_name, "Most Selected Clubs", "Count", "Club")
            st.plotly_chart(fig3)

    elif page == "Similarity Analyser":

        # Set up the Streamlit app
        st.markdown(f'<p class="big-font">Similarity Analyser - Game Week {selected_game_week}</p>', unsafe_allow_html=True)
        st.markdown(f'Select 2 teams and see how similar they are to each other.')

        # Entry Name filter
        entry_names = sorted(df_Full_Selection_Data['entry_name'].unique())

        # Add custom CSS to center the content in each column
        st.markdown(
            """
            <style>
            .stSelectbox {
                text-align: left;
            }
            div[data-testid="column"] {
                display: flex;
                flex-direction: column;
                justify-content: left;
                align-items: left;
            }
            </style>
            """, unsafe_allow_html=True
        )

        col1, col2 = st.columns(2)        
        with col1:
            team_1 = st.selectbox('Select Team 1', entry_names)
        with col2:
            team_2 = st.selectbox('Select Team 2', entry_names)

        # Add a horizontal dividing line
        st.markdown("---")

        # Check if the user selects the same team for both
        if team_1 == team_2:
            st.warning("Warning: You have selected the same team for both Team 1 and Team 2. Please choose 2 different teams.")
        else:
            df_team_1 = df_Full_Selection_Data[(df_Full_Selection_Data['game_week'] == selected_game_week) 
                                            & (df_Full_Selection_Data['entry_name'] == team_1)]
            
            df_team_2 = df_Full_Selection_Data[(df_Full_Selection_Data['game_week'] == selected_game_week) 
                                            & (df_Full_Selection_Data['entry_name'] == team_2)]
            
            similarity, similar_df, only_df1, only_df2 = calculate_similarity_score(df_team_1, df_team_2)

            # display teams
            st.markdown(f"<p class='medium-font'>{team_1} vs {team_2} | Similarity Score: {similarity}%</p>", unsafe_allow_html=True)

            # List of mysterious explanations
            mystery_lines = [
                "~ Calculated by the FPL wizards at the break of dawn. 🧙‍♂️",
                "~ Derived from the Sun, the Moon and Football Stars... ✨",
                "~ Forged in the fires of forgotten Puskas Award Winners. 🔥💀",
                "~ Friends are like mirrors 🪞, they reflect who we are and help us grow in ways we never imagined."
            ]
            # Randomly choose one explanation
            st.markdown(f'<p class="creator">{random.choice(mystery_lines)}</p>', unsafe_allow_html=True)

            st.markdown("")
            st.subheader('Similar Players')
            st.dataframe(cleanse_similar_df(similar_df, team_1, team_2))

            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.subheader(f'Players only in {team_1}')
                st.dataframe(cleanse_onlydf(only_df1))
            with col2:
                st.subheader(f'Players only in {team_2}')
                st.dataframe(cleanse_onlydf(only_df2))

            st.markdown("---")

            # Collapsible section
            with st.expander("View the League's Similarity Matrix"):
                st.write("This content is hidden by default and can be expanded or collapsed.")
                st.write("Add more content here as needed, like text, charts, or tables.")

    elif page == "Transfer Statistics":

        st.markdown(f'<p class="big-font">Transfer Statistics - Game Week {selected_game_week}</p>', unsafe_allow_html=True)

        df_time = df_All_Transfers[['time_SG', 'entry_name', 'name_PlayerIn', 
                                    'id_player_PlayerIn', 'web_name_PlayerIn', 'element_in_cost',
                                    'name_PlayerOut', 'id_player_PlayerOut', 'web_name_PlayerOut', 'element_out_cost']]

        # Convert 'DateTime' to pandas datetime if it's not already in datetime format
        df_time['DateTime'] = pd.to_datetime(df_time['time_SG'])

        # Extract additional time features from the DateTime column
        df_time['Date'] = df_time['DateTime'].dt.date
        df_time['Day of Week'] = df_time['DateTime'].dt.day_name()
        
        # Convert hour to 12-hour format without leading zeros and with AM/PM
        df_time['Hour of the Day'] = df_time['DateTime'].dt.hour % 12  # Get hour in 12-hour format (0-11)
        df_time['Hour of the Day'] = df_time['Hour of the Day'].replace(0, 12)  # Replace 0 with 12 for midnight
        df_time['Hour of the Day'] = df_time['Hour of the Day'].astype(str) + ' ' + df_time['DateTime'].dt.strftime('%p')  # Concatenate AM/PM  # %-I removes leading zero for single-digit hours

        # Arrange DayOfWeek in correct order (Monday to Sunday)
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        df_time['Day of Week'] = pd.Categorical(df_time['Day of Week'], categories=day_order, ordered=True)

        # Define the correct ordering for the 12-hour format (from 12 AM to 11 PM)
        hour_order = ['12 AM', '1 AM', '2 AM', '3 AM', '4 AM', '5 AM', '6 AM', '7 AM', 
                    '8 AM', '9 AM', '10 AM', '11 AM', 
                    '12 PM', '1 PM', '2 PM', '3 PM', '4 PM', '5 PM', '6 PM', '7 PM', 
                    '8 PM', '9 PM', '10 PM', '11 PM']

        df_time['Hour of the Day'] = pd.Categorical(df_time['Hour of the Day'], categories=hour_order, ordered=True)

        # st.dataframe(df_time)

        # Streamlit app
        st.title('Transfer Activity Chart')

        # X-axis selection
        x_axis = st.selectbox("Select X-axis", ["Date", "Day of Week", "Hour of the Day"])

        # Define the metric for y-axis
        df_time['Transfer Count'] = 1  # For each transfer, count 1 occurrence

        # Group by the selected x-axis column and aggregate the count
        if x_axis == "Date":
            df_grouped = df_time.groupby('Date').agg({'Transfer Count': 'sum'}).reset_index()
        elif x_axis == "Day of Week":
            df_grouped = df_time.groupby('Day of Week').agg({'Transfer Count': 'sum'}).reset_index()
        elif x_axis == "Hour of the Day":
            df_grouped = df_time.groupby('Hour of the Day').agg({'Transfer Count': 'sum'}).reset_index()

        # Plot the bar chart based on selected x-axis
        fig = px.bar(df_grouped, x=df_grouped.columns[0], y='Transfer Count', 
                    title=f"Transfers by {x_axis}", 
                    hover_data={'Transfer Count': True},  # Show total count in hover tooltip
                    category_orders={
                        'Day of Week': day_order, 
                        'Hour of the Day': hour_order
                    } if x_axis in ["Day of Week", "Hour of the Day"] else None)
        
        fig.update_traces(marker_color='#00ff87')

        # Display the Plotly figure in Streamlit
        st.plotly_chart(fig)                            
else:
    home()