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

- streamlit
- pandas
- plotly
- numpy
- API_Extraction (custom module for FPL data retrieval)

## Data Source

This dashboard uses the official Fantasy Premier League API to fetch data. The `API_Extraction` module (not included in this repository) is responsible for making API calls and initial data processing.

## Contributing

Contributions to improve the dashboard are welcome. Please feel free to submit a Pull Request or open an Issue for any bugs or feature requests.

## License

[MIT License](LICENSE)

## Disclaimer

This project is not affiliated with or endorsed by the official Fantasy Premier League or Premier League. It is a fan-made tool intended for personal use and analysis.

