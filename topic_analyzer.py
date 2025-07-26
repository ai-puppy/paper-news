"""LangChain-based topic analyzer for YouTube video data."""

import os
import uuid
from typing import List, Dict, Tuple
from collections import Counter
import pandas as pd
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain.schema import Document
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()


class TopicAnalyzer:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        self.embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))
        
    def extract_topics(self, videos: List[Dict]) -> List[Dict]:
        """
        Extract main topics from video titles and descriptions.
        
        Args:
            videos: List of video dictionaries
            
        Returns:
            List of videos with extracted topics
        """
        topic_extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at analyzing video content and extracting main topics.
            Extract the main topics from the video title and description.
            Focus on technical topics, frameworks, tools, and concepts.
            Return a JSON object with 'main_topic' and 'subtopics' (list of 3-5 subtopics)."""),
            ("user", "Title: {title}\n\nDescription: {description}")
        ])
        
        json_parser = JsonOutputParser()
        chain = topic_extraction_prompt | self.llm | json_parser
        
        for video in videos:
            try:
                result = chain.invoke({
                    "title": video["title"],
                    "description": video.get("description", "")[:500]  # Limit description length
                })
                
                video["main_topic"] = result.get("main_topic", "")
                video["subtopics"] = result.get("subtopics", [])
                
            except Exception as e:
                print(f"Error extracting topics for video {video['video_id']}: {e}")
                video["main_topic"] = ""
                video["subtopics"] = []
                
        return videos
    
    def cluster_similar_topics(self, videos: List[Dict], similarity_threshold: float = 0.7) -> Dict[str, List[Dict]]:
        """
        Cluster videos by similar topics using embeddings and semantic similarity.
        
        Args:
            videos: List of videos with extracted topics
            similarity_threshold: Minimum similarity score to consider videos as related (0-1)
            
        Returns:
            Dictionary mapping cluster topics to lists of videos
        """
        if not videos:
            return {}
            
        # Create a mapping of video_id to video for easy lookup
        video_map = {v["video_id"]: v for v in videos}
        
        # Create documents from video topics
        documents = []
        video_ids = []
        for video in videos:
            if video.get("main_topic"):
                text = f"{video['main_topic']} {' '.join(video.get('subtopics', []))}"
                doc = Document(
                    page_content=text,
                    metadata={
                        "video_id": video["video_id"], 
                        "title": video["title"],
                        "main_topic": video["main_topic"]
                    }
                )
                documents.append(doc)
                video_ids.append(video["video_id"])
        
        if not documents:
            return {}
            
        # Create vector store for similarity search
        # Use a unique collection name to avoid conflicts
        collection_name = f"video_topics_{uuid.uuid4().hex[:8]}"
        
        vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            collection_name=collection_name
        )
        
        # Find clusters using semantic similarity
        clustered_videos = {}
        processed_video_ids = set()
        
        # Sort videos by view count to start clustering from most popular videos
        sorted_videos = sorted(videos, key=lambda x: x.get("view_count", 0), reverse=True)
        
        for seed_video in sorted_videos:
            if seed_video["video_id"] in processed_video_ids:
                continue
                
            if not seed_video.get("main_topic"):
                continue
            
            # Search for semantically similar videos
            query_text = f"{seed_video['main_topic']} {' '.join(seed_video.get('subtopics', []))}"
            similar_docs = vectorstore.similarity_search_with_score(
                query_text, 
                k=min(20, len(documents))  # Get up to 20 similar videos
            )
            
            # Group similar videos together
            cluster_videos = []
            cluster_topics = []
            
            for doc, score in similar_docs:
                # Use similarity threshold
                if score <= (1 - similarity_threshold):  # Chroma returns distance, not similarity
                    video_id = doc.metadata["video_id"]
                    if video_id not in processed_video_ids:
                        cluster_videos.append(video_map[video_id])
                        cluster_topics.append(doc.metadata["main_topic"])
                        processed_video_ids.add(video_id)
            
            if len(cluster_videos) >= 2:  # Only create cluster if we have at least 2 videos
                # Generate cluster name based on common topics
                cluster_name = self._generate_cluster_name(cluster_topics)
                clustered_videos[cluster_name] = cluster_videos
        
        # Add unclustered videos
        unclustered = [v for v in videos if v["video_id"] not in processed_video_ids]
        if unclustered:
            # Try to group unclustered videos by exact topic match
            remaining_groups = {}
            for video in unclustered:
                topic = video.get("main_topic", "Other Topics")
                if topic not in remaining_groups:
                    remaining_groups[topic] = []
                remaining_groups[topic].append(video)
            
            # Add groups with multiple videos as clusters
            for topic, vids in remaining_groups.items():
                if len(vids) >= 2:
                    clustered_videos[topic] = vids
                else:
                    # Single videos go to "Other Topics"
                    if "Other Topics" not in clustered_videos:
                        clustered_videos["Other Topics"] = []
                    clustered_videos["Other Topics"].extend(vids)
            
        return clustered_videos
    
    def _generate_cluster_name(self, topics: List[str]) -> str:
        """
        Generate a descriptive name for a cluster based on its topics.
        
        Args:
            topics: List of main topics in the cluster
            
        Returns:
            A descriptive cluster name
        """
        if not topics:
            return "Other Topics"
            
        # Count topic frequencies
        topic_counts = Counter(topics)
        most_common = topic_counts.most_common(3)
        
        # If there's a dominant topic, use it
        if most_common[0][1] >= len(topics) * 0.5:
            return most_common[0][0]
        
        # Otherwise, use LLM to generate a name
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", "Generate a concise, descriptive name for a group of related topics. Return only the name, nothing else."),
                ("user", "Topics: {topics}")
            ])
            
            chain = prompt | self.llm
            result = chain.invoke({"topics": ", ".join(set(topics[:10]))})
            return result.content.strip()
        except:
            # Fallback to most common topic
            return most_common[0][0] if most_common else "Other Topics"
    
    def calculate_trend_scores(self, clustered_videos: Dict[str, List[Dict]]) -> List[Dict]:
        """
        Calculate trend scores for each topic cluster based on engagement metrics.
        
        Args:
            clustered_videos: Dictionary mapping topics to videos
            
        Returns:
            List of trend dictionaries sorted by score
        """
        trends = []
        
        for topic, videos in clustered_videos.items():
            if not videos:
                continue
                
            # Calculate aggregate metrics
            total_views = sum(v.get("view_count", 0) for v in videos)
            total_likes = sum(v.get("like_count", 0) for v in videos)
            total_comments = sum(v.get("comment_count", 0) for v in videos)
            video_count = len(videos)
            
            # Calculate average engagement rate
            avg_engagement_rate = 0
            if total_views > 0:
                avg_engagement_rate = (total_likes + total_comments) / total_views
            
            # Calculate trend score (weighted combination of metrics)
            # Higher weight for engagement rate and video count (indicating topic popularity)
            trend_score = (
                (total_views / 1000) * 0.2 +  # Views impact (scaled down)
                avg_engagement_rate * 10000 * 0.4 +  # Engagement rate (scaled up)
                video_count * 10 * 0.4  # Number of videos on topic
            )
            
            trends.append({
                "topic": topic,
                "trend_score": round(trend_score, 2),
                "video_count": video_count,
                "total_views": total_views,
                "total_likes": total_likes,
                "total_comments": total_comments,
                "avg_engagement_rate": round(avg_engagement_rate * 100, 2),  # As percentage
                "top_videos": sorted(videos, key=lambda x: x.get("view_count", 0), reverse=True)[:5]
            })
        
        # Sort by trend score
        trends.sort(key=lambda x: x["trend_score"], reverse=True)
        
        return trends
    
    def generate_insights(self, trends: List[Dict], area_of_interest: str) -> str:
        """
        Generate insights about the trending topics.
        
        Args:
            trends: List of trend dictionaries
            area_of_interest: The area user is interested in
            
        Returns:
            Insights text
        """
        insights_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert analyst providing insights on trending topics.
            Analyze the trend data and provide actionable insights.
            Focus on:
            1. What topics are currently most popular
            2. Why these topics might be trending
            3. Emerging topics to watch
            4. Recommendations for content creators or learners
            Keep the insights concise and actionable."""),
            ("user", "Area of Interest: {area}\n\nTop Trends:\n{trends_data}")
        ])
        
        # Prepare trends data for the prompt
        trends_summary = []
        for i, trend in enumerate(trends[:10]):  # Top 10 trends
            trends_summary.append(
                f"{i+1}. {trend['topic']}: "
                f"Score={trend['trend_score']}, "
                f"Videos={trend['video_count']}, "
                f"Engagement={trend['avg_engagement_rate']}%"
            )
        
        chain = insights_prompt | self.llm
        
        try:
            insights = chain.invoke({
                "area": area_of_interest,
                "trends_data": "\n".join(trends_summary)
            })
            return insights.content
        except Exception as e:
            print(f"Error generating insights: {e}")
            return "Unable to generate insights at this time."