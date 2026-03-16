"""
Playwright integration tests for OpenCommish Streamlit Dashboard.

These tests verify that the dashboard loads correctly and all pages are accessible.
Run with: pytest tests/integration/ --browser chromium
"""

import pytest
from playwright.sync_api import Page, expect


class TestDashboardOverview:
    """Tests for the Overview page."""
    
    def test_page_loads(self, dashboard_page: Page):
        """Verify the dashboard loads and shows the main header."""
        # Check for main header
        expect(dashboard_page.locator("text=OpenCommish")).to_be_visible()
        expect(dashboard_page.locator("text=🏀")).to_be_visible()
    
    def test_sidebar_navigation_present(self, dashboard_page: Page):
        """Verify sidebar navigation is present."""
        # Streamlit radio buttons for navigation
        nav_options = ["📊 Overview", "🏆 Team Rankings", "⭐ Player Analysis", "📈 Trends", "💔 Bench Efficiency"]
        for option in nav_options:
            expect(dashboard_page.locator(f"text={option}")).to_be_visible()
    
    def test_key_metrics_display(self, dashboard_page: Page):
        """Verify key metrics are displayed on overview."""
        # Look for common metric labels
        expect(dashboard_page.locator("text=Total Fantasy Points")).to_be_visible()
        expect(dashboard_page.locator("text=Total Players")).to_be_visible()


class TestTeamRankings:
    """Tests for the Team Rankings page."""
    
    def test_navigate_to_rankings(self, dashboard_page: Page):
        """Navigate to Team Rankings page."""
        dashboard_page.click("text=🏆 Team Rankings")
        # Wait for page to load
        dashboard_page.wait_for_timeout(1000)
        expect(dashboard_page.locator("text=Team Rankings")).to_be_visible()
    
    def test_rankings_table_exists(self, dashboard_page: Page):
        """Verify rankings table is displayed."""
        dashboard_page.click("text=🏆 Team Rankings")
        dashboard_page.wait_for_timeout(1000)
        # Look for table elements
        expect(dashboard_page.locator("text=Fantasy Pts")).to_be_visible()


class TestPlayerAnalysis:
    """Tests for the Player Analysis page."""
    
    def test_navigate_to_player_analysis(self, dashboard_page: Page):
        """Navigate to Player Analysis page."""
        dashboard_page.click("text=⭐ Player Analysis")
        dashboard_page.wait_for_timeout(1000)
        expect(dashboard_page.locator("text=Player Analysis")).to_be_visible()
    
    def test_filters_present(self, dashboard_page: Page):
        """Verify filter controls are present."""
        dashboard_page.click("text=⭐ Player Analysis")
        dashboard_page.wait_for_timeout(1000)
        # Look for selectbox labels
        expect(dashboard_page.locator("text=Select Team")).to_be_visible()


class TestTrends:
    """Tests for the Trends page."""
    
    def test_navigate_to_trends(self, dashboard_page: Page):
        """Navigate to Trends page."""
        dashboard_page.click("text=📈 Trends")
        dashboard_page.wait_for_timeout(1000)
        expect(dashboard_page.locator("text=Trends")).to_be_visible()
    
    def test_trend_chart_exists(self, dashboard_page: Page):
        """Verify trend charts are displayed."""
        dashboard_page.click("text=📈 Trends")
        dashboard_page.wait_for_timeout(1000)
        # Look for plotly chart container
        charts = dashboard_page.locator(".js-plotly-plot")
        expect(charts.first).to_be_visible()


class TestBenchEfficiency:
    """Tests for the Bench Efficiency page."""
    
    def test_navigate_to_bench(self, dashboard_page: Page):
        """Navigate to Bench Efficiency page."""
        dashboard_page.click("text=💔 Bench Efficiency")
        dashboard_page.wait_for_timeout(1000)
        expect(dashboard_page.locator("text=Bench Efficiency")).to_be_visible()
    
    def test_bench_metrics_display(self, dashboard_page: Page):
        """Verify bench efficiency metrics are displayed."""
        dashboard_page.click("text=💔 Bench Efficiency")
        dashboard_page.wait_for_timeout(1000)
        expect(dashboard_page.locator("text=Points Left on Bench")).to_be_visible()


class TestDataLoading:
    """Tests for data loading and error handling."""
    
    def test_data_available_message(self, dashboard_page: Page):
        """Verify data is being loaded."""
        # Should not show "No data available" if data exists
        no_data_msg = dashboard_page.locator("text=No data available")
        # If data exists, this should not be visible
        if no_data_msg.count() > 0:
            expect(no_data_msg).not_to_be_visible()
