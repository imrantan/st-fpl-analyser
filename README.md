# Fantasy Premier League Dashboard

## Overview

This Streamlit application provides a comprehensive dashboard for analyzing Fantasy Premier League (FPL) data. It offers insights into individual team performance and overall league statistics, making it a valuable tool for FPL managers to track their progress and make informed decisions.

## Features

- **League Overview**: 
  - View overall league performance metrics
  - See team rankings and performance across game weeks
  - Analyze league-wide trends in player selection and captain choices

- **Individual Team Analysis**:
  - Detailed breakdown of team performance for each game week
  - View first eleven and bench player statistics
  - Track transfers and their impact on team performance

- **Interactive Visualizations**:
  - Line charts showing team performance across game weeks
  - Bar charts displaying player points, most captained players, and most selected players/clubs

- **Flexible Filters**:
  - Select specific game weeks for analysis
  - Choose different leagues using league IDs
  - Filter data for individual teams within a league

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/fantasy-premier-league-dashboard.git
   cd fantasy-premier-league-dashboard
   ```

2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Run the Streamlit app:
   ```
   streamlit run app.py
   ```

2. Open your web browser and go to `http://localhost:8501`.

3. In the sidebar, enter a valid FPL league ID and click 'Update' to load the data.

4. Use the navigation options in the sidebar to switch between "Overall League" and "Individual Team Overview" pages.

5. Explore the various charts and statistics available on each page.

## Dependencies

numpy==1.26.4
plotly==5.23.0
pandas==2.2.1
tqdm==4.66.5
pytz==2024.1
streamlit==1.37.1
toml==0.10.2

## Data Source and API Extraction

This dashboard uses the official Fantasy Premier League API to fetch data. The `API_Extraction` module is responsible for making API calls and initial data processing. Here's an overview of its functionality:

- Retrieves data up to a specified game week for a given league ID
- Fetches league standings, team selections, player statistics, and transfer information
- Processes and combines data from multiple API endpoints
- Performs data validation and error checking
- Handles time zone conversion for transfer data

The module returns the following key data structures:
- League name
- Historical team data
- Full player selection data
- All transfers data
- Processed transfers data (ins and outs)

Note: The API extraction process may take some time, especially for larger leagues or when fetching data for many game weeks.

## Author

This Fantasy Premier League Dashboard was created by Imran Tan. As an avid FPL player and data enthusiast, Imran developed this tool to help fellow FPL Managers gain deeper insights into their league performance and make data-driven decisions for their teams.

## Contributing

Contributions to improve the dashboard are welcome. Please feel free to submit a Pull Request or open an Issue for any bugs or feature requests.

## License

[MIT License](LICENSE)

## Disclaimer

This project is not affiliated with or endorsed by the official Fantasy Premier League or Premier League. It is a fan-made tool intended for personal use and analysis. Please use responsibly and in accordance with the Fantasy Premier League's terms of service.