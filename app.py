"""Streamlit app for YouTube trend analysis."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from youtube_client import YouTubeClient
from topic_analyzer import TopicAnalyzer
from api_utils import QuotaExceededError, YouTubeAPIError

# Page config
st.set_page_config(
    page_title="YouTube Trend Analyzer",
    page_icon="📊",
    layout="wide"
)

# Title and description
st.title("📊 YouTube Trend Analyzer")
st.markdown("Discover trending topics in your area of interest by analyzing YouTube video data")

# Sidebar inputs
with st.sidebar:
    st.header("Configuration")
    
    area_of_interest = st.text_input(
        "Area of Interest",
        value="AI agents, LLM, coding",
        help="Enter keywords for your area of interest, separated by commas"
    )
    
    time_range = st.selectbox(
        "Time Range",
        options=[1, 3, 7, 14, 30],
        index=2,
        format_func=lambda x: f"Last {x} days"
    )
    
    max_videos = st.slider(
        "Number of Videos to Analyze",
        min_value=10,
        max_value=100,
        value=50,
        step=10
    )
    
    sort_order = st.selectbox(
        "Sort Videos By",
        options=["relevance", "date", "viewCount", "rating"],
        index=0
    )
    
    analyze_button = st.button("🔍 Analyze Trends", type="primary", use_container_width=True)

# Main content area
if analyze_button:
    try:
        # Initialize clients
        youtube_client = YouTubeClient()
        topic_analyzer = TopicAnalyzer()
        
        # Create progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Step 1: Fetch videos
        status_text.text("Fetching YouTube videos...")
        progress_bar.progress(20)
        
        videos = youtube_client.search_videos(
            query=area_of_interest,
            max_results=max_videos,
            days_back=time_range,
            order=sort_order
        )
        
        if not videos:
            st.error("No videos found for the given search criteria.")
            st.stop()
        
        # Step 2: Get video statistics
        status_text.text("Fetching video statistics...")
        progress_bar.progress(40)
        
        video_ids = [v["video_id"] for v in videos]
        stats = youtube_client.get_video_statistics(video_ids)
        
        # Merge statistics with video data
        for video in videos:
            video_stats = stats.get(video["video_id"], {})
            video.update(video_stats)
        
        # Step 3: Extract topics
        status_text.text("Analyzing topics with AI...")
        progress_bar.progress(60)
        
        videos_with_topics = topic_analyzer.extract_topics(videos)
        
        # Step 4: Cluster topics
        status_text.text("Clustering similar topics...")
        progress_bar.progress(80)
        
        # Use semantic similarity for clustering with configurable threshold
        similarity_threshold = 0.7  # Can be made configurable in sidebar
        clustered_videos = topic_analyzer.cluster_similar_topics(videos_with_topics, similarity_threshold)
        
        # Step 5: Calculate trend scores
        status_text.text("Calculating trend scores...")
        progress_bar.progress(90)
        
        trends = topic_analyzer.calculate_trend_scores(clustered_videos)
        
        # Step 6: Generate insights
        status_text.text("Generating insights...")
        insights = topic_analyzer.generate_insights(trends, area_of_interest)
        
        progress_bar.progress(100)
        status_text.text("Analysis complete!")
        
        # Display results
        st.header("📈 Analysis Results")
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Videos Analyzed", len(videos))
        with col2:
            st.metric("Topics Identified", len(trends))
        with col3:
            total_views = sum(v.get("view_count", 0) for v in videos)
            st.metric("Total Views", f"{total_views:,}")
        with col4:
            avg_engagement = sum(t["avg_engagement_rate"] for t in trends) / len(trends) if trends else 0
            st.metric("Avg Engagement", f"{avg_engagement:.2f}%")
        
        # Quota status
        quota_status = youtube_client.get_quota_status()
        st.caption(f"API Quota: {quota_status['used']:,} / {quota_status['limit']:,} units used ({quota_status['remaining']:,} remaining)")
        
        # AI Insights
        st.header("🤖 AI Insights")
        st.info(insights)
        
        # Trending Topics Chart
        st.header("🔥 Trending Topics")
        
        if trends:
            # Create DataFrame for visualization
            trends_df = pd.DataFrame(trends[:10])  # Top 10 trends
            
            # Bar chart of trend scores
            fig_bar = px.bar(
                trends_df,
                x="trend_score",
                y="topic",
                orientation="h",
                title="Top 10 Trending Topics by Score",
                labels={"trend_score": "Trend Score", "topic": "Topic"},
                color="trend_score",
                color_continuous_scale="Reds"
            )
            fig_bar.update_layout(height=500, showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)
            
            # Scatter plot: Views vs Engagement
            fig_scatter = px.scatter(
                trends_df,
                x="total_views",
                y="avg_engagement_rate",
                size="video_count",
                color="trend_score",
                hover_data=["topic", "video_count"],
                title="Topic Popularity: Views vs Engagement Rate",
                labels={
                    "total_views": "Total Views",
                    "avg_engagement_rate": "Avg Engagement Rate (%)",
                    "video_count": "Number of Videos"
                },
                color_continuous_scale="Viridis"
            )
            fig_scatter.update_layout(height=500)
            st.plotly_chart(fig_scatter, use_container_width=True)
        
        # Detailed Topic Analysis
        st.header("📋 Detailed Topic Analysis")
        
        for i, trend in enumerate(trends[:5]):  # Top 5 trends
            with st.expander(f"#{i+1} {trend['topic']} (Score: {trend['trend_score']})"):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Videos", trend["video_count"])
                with col2:
                    st.metric("Total Views", f"{trend['total_views']:,}")
                with col3:
                    st.metric("Total Likes", f"{trend['total_likes']:,}")
                with col4:
                    st.metric("Engagement Rate", f"{trend['avg_engagement_rate']}%")
                
                st.subheader("Top Videos")
                for video in trend["top_videos"]:
                    st.write(f"**{video['title']}**")
                    st.caption(f"Channel: {video['channel_title']} | Views: {video.get('view_count', 0):,}")
                    st.write("---")
        
        # Raw data export
        st.header("💾 Export Data")
        
        # Prepare export data
        export_data = []
        for trend in trends:
            export_data.append({
                "Topic": trend["topic"],
                "Trend Score": trend["trend_score"],
                "Video Count": trend["video_count"],
                "Total Views": trend["total_views"],
                "Total Likes": trend["total_likes"],
                "Total Comments": trend["total_comments"],
                "Avg Engagement Rate (%)": trend["avg_engagement_rate"]
            })
        
        export_df = pd.DataFrame(export_data)
        csv = export_df.to_csv(index=False)
        
        st.download_button(
            label="📥 Download Trend Analysis (CSV)",
            data=csv,
            file_name=f"youtube_trends_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
        
    except ValueError as e:
        st.error(f"Configuration Error: {str(e)}")
        st.info("Please make sure you have set up your API keys in the .env file")
    except QuotaExceededError as e:
        st.error(f"API Quota Exceeded: {str(e)}")
        st.info("The YouTube API daily quota has been exceeded. Please try again tomorrow or use a different API key.")
    except YouTubeAPIError as e:
        st.error(f"YouTube API Error: {str(e)}")
        st.info("There was an issue with the YouTube API. Please check your API key and try again.")
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        st.info("Please check your configuration and try again")

else:
    # Instructions when not analyzing
    st.info("""
    👈 Configure your search parameters in the sidebar and click **Analyze Trends** to start.
    
    **How it works:**
    1. Fetches recent YouTube videos based on your area of interest
    2. Analyzes video titles and descriptions using AI to extract topics
    3. Clusters similar topics together
    4. Calculates trend scores based on views, likes, comments, and engagement
    5. Provides AI-generated insights about the trending topics
    
    **Tips:**
    - Use specific keywords for better results (e.g., "LangChain agents" instead of just "AI")
    - Longer time ranges give more comprehensive trends
    - More videos analyzed means better topic clustering
    """)
    
    # Show example
    with st.expander("📸 See Example Output"):
        st.image("https://via.placeholder.com/800x400?text=Example+Trend+Analysis+Chart", 
                caption="Example trend analysis visualization")

# Footer
st.markdown("---")
st.caption("Built with Streamlit, LangChain, and YouTube Data API")