"""
Instagram Engagement Scraper using Playwright

Installation:
pip install playwright
playwright install chromium

Usage:
python script.py
"""

from playwright.sync_api import sync_playwright
import json
import time
from datetime import datetime
import re
import argparse

class InstagramEngagementScraper:
    def __init__(self, headless=False, guest_mode=True):
        """guest_mode: when True, avoid logging in and use public JSON endpoints as fallback"""
        self.headless = headless
        self.guest_mode = guest_mode
        self.engagement_data = {}
    
    def scrape_profile(self, username):
        """Scrape Instagram profile and calculate engagement metrics"""
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            
            try:
                print(f"Scraping profile: {username}")
                url = f"https://www.instagram.com/{username}/"
                page.goto(url, wait_until='networkidle', timeout=30000)

                # Wait for content to load
                time.sleep(3)

                # Get profile stats and posts (try page first)
                profile_data = self._extract_profile_stats(page)
                posts_data = self._extract_posts_data(page, max_posts=12)

                # If running in guest mode or page scraping failed (Instagram shows login wall),
                # try the JSON endpoint fallback which often works for public profiles.
                login_wall_texts = [
                    'Log in to see', 'Log in to continue', 'Log in to view', 'Only people who follow'
                ]
                page_text = ''
                try:
                    page_text = page.content()
                except:
                    pass

                need_fallback = (self.guest_mode or profile_data.get('followers', 0) == 0 or len(posts_data) == 0)
                for t in login_wall_texts:
                    if t.lower() in page_text.lower():
                        need_fallback = True
                        break

                if need_fallback:
                    try:
                        json_profile, json_posts = self._fetch_profile_json(username, p)
                        if json_profile:
                            profile_data = json_profile
                        if json_posts:
                            posts_data = json_posts
                    except Exception as e:
                        print(f"JSON fallback failed: {e}")
                
                # Calculate engagement metrics
                engagement_metrics = self._calculate_engagement(profile_data, posts_data)
                
                result = {
                    **profile_data,
                    **engagement_metrics,
                    'posts_analyzed': len(posts_data),
                    'timestamp': datetime.now().isoformat()
                }
                
                print(f"\n{'='*60}")
                print(f"ENGAGEMENT REPORT: @{username}")
                print(f"{'='*60}")
                self._print_report(result)
                
                return result
                
            except Exception as e:
                print(f"Error: {str(e)}")
                return None
            
            finally:
                browser.close()
    
    def _extract_profile_stats(self, page):
        """Extract follower count, following, and post count"""
        
        data = {
            'followers': 0,
            'following': 0,
            'total_posts': 0
        }
        
        try:
            # Method 1: Try to get from meta tags
            page.wait_for_selector('meta[property="og:description"]', timeout=5000)
            meta_desc = page.get_attribute('meta[property="og:description"]', 'content')
            
            if meta_desc:
                # Parse: "X Followers, Y Following, Z Posts"
                numbers = re.findall(r'([\d,]+)\s*(Followers|Following|Posts)', meta_desc)
                for num, label in numbers:
                    clean_num = int(num.replace(',', ''))
                    if 'Follower' in label:
                        data['followers'] = clean_num
                    elif 'Following' in label:
                        data['following'] = clean_num
                    elif 'Post' in label:
                        data['total_posts'] = clean_num
            
            # Method 2: Try to get from page text
            if data['followers'] == 0:
                try:
                    # Look for spans or links containing stats
                    stats = page.locator('header section ul li').all()
                    for i, stat in enumerate(stats[:3]):
                        text = stat.inner_text()
                        number = re.search(r'([\d,\.]+[KMB]?)', text)
                        if number:
                            value = self._convert_to_number(number.group(1))
                            if i == 0:
                                data['total_posts'] = value
                            elif i == 1:
                                data['followers'] = value
                            elif i == 2:
                                data['following'] = value
                except:
                    pass
            
        except Exception as e:
            print(f"Warning: Could not extract all profile stats - {str(e)}")
        
        return data

    def _fetch_profile_json(self, username, playwright_obj):
        """Try to fetch public profile data using Instagram's public JSON endpoint.

        Returns (profile_data_dict, posts_list)
        """
        profile = {'followers': 0, 'following': 0, 'total_posts': 0}
        posts = []

        try:
            # Use Playwright's request API to avoid being blocked by page overlays
            url = f'https://www.instagram.com/{username}/?__a=1&__d=dis'
            resp = playwright_obj.request.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json'
            }, timeout=15000)

            if resp.status != 200:
                raise Exception(f'HTTP {resp.status}')

            data = resp.json()

            # Newer responses include graphql -> user
            user = data.get('graphql', {}).get('user') or data.get('profile')
            if user:
                profile['followers'] = user.get('edge_followed_by', {}).get('count', 0)
                profile['following'] = user.get('edge_follow', {}).get('count', 0)
                profile['total_posts'] = user.get('edge_owner_to_timeline_media', {}).get('count', 0)

                edges = user.get('edge_owner_to_timeline_media', {}).get('edges', [])
                for edge in edges[:12]:
                    node = edge.get('node', {})
                    likes = node.get('edge_liked_by', {}).get('count', 0)
                    comments = node.get('edge_media_to_comment', {}).get('count', 0)
                    posts.append({'likes': likes, 'comments': comments})

        except Exception as e:
            print(f"Warning: JSON profile fetch failed: {e}")

        return profile, posts
    
    def _extract_posts_data(self, page, max_posts=12):
        """Extract engagement data from recent posts"""
        
        posts = []
        
        try:
            # Wait for posts to load
            page.wait_for_selector('article', timeout=10000)
            time.sleep(2)
            
            # Scroll to load more posts
            for _ in range(3):
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(2)
            
            # Get all post links
            post_links = page.locator('article a[href*="/p/"]').all()[:max_posts]
            
            print(f"Found {len(post_links)} posts to analyze...")
            
            for i, link in enumerate(post_links, 1):
                try:
                    href = link.get_attribute('href')
                    post_url = f"https://www.instagram.com{href}" if href.startswith('/') else href
                    
                    print(f"Analyzing post {i}/{len(post_links)}...")
                    
                    # Open post in new page
                    post_page = page.context.new_page()
                    post_page.goto(post_url, wait_until='networkidle', timeout=20000)
                    time.sleep(2)
                    
                    post_data = self._extract_post_engagement(post_page)
                    if post_data:
                        posts.append(post_data)
                    
                    post_page.close()
                    time.sleep(1)  # Be nice to Instagram's servers
                    
                except Exception as e:
                    print(f"Error on post {i}: {str(e)}")
                    continue
        
        except Exception as e:
            print(f"Error extracting posts: {str(e)}")
        
        return posts
    
    def _extract_post_engagement(self, page):
        """Extract likes and comments from a single post"""
        
        data = {
            'likes': 0,
            'comments': 0
        }
        
        try:
            # Try to find likes
            like_selectors = [
                'section span[class*="xdj266r"]',  # Common like counter class
                'section button span',
                'a[href*="/liked_by/"] span'
            ]
            
            for selector in like_selectors:
                try:
                    elements = page.locator(selector).all()
                    for elem in elements:
                        text = elem.inner_text()
                        if 'like' in text.lower() or re.match(r'^[\d,\.]+[KMB]?\s*$', text):
                            number = re.search(r'([\d,\.]+[KMB]?)', text)
                            if number:
                                data['likes'] = self._convert_to_number(number.group(1))
                                break
                    if data['likes'] > 0:
                        break
                except:
                    continue
            
            # Try to find comments
            comment_selectors = [
                'span:has-text("comment")',
                'ul li span'
            ]
            
            for selector in comment_selectors:
                try:
                    elements = page.locator(selector).all()
                    for elem in elements:
                        text = elem.inner_text()
                        if 'comment' in text.lower():
                            number = re.search(r'([\d,\.]+[KMB]?)', text)
                            if number:
                                data['comments'] = self._convert_to_number(number.group(1))
                                break
                    if data['comments'] > 0:
                        break
                except:
                    continue
            
            # Fallback: count visible comments
            if data['comments'] == 0:
                try:
                    comment_items = page.locator('ul ul li[role="menuitem"]').count()
                    data['comments'] = comment_items
                except:
                    pass
        
        except Exception as e:
            print(f"Error extracting post engagement: {str(e)}")
        
        return data if data['likes'] > 0 or data['comments'] > 0 else None
    
    def _calculate_engagement(self, profile_data, posts_data):
        """Calculate engagement metrics"""
        
        if not posts_data or profile_data['followers'] == 0:
            return {
                'avg_likes': 0,
                'avg_comments': 0,
                'avg_total_engagement': 0,
                'engagement_rate': 0
            }
        
        total_likes = sum(p['likes'] for p in posts_data)
        total_comments = sum(p['comments'] for p in posts_data)
        num_posts = len(posts_data)
        
        avg_likes = total_likes / num_posts
        avg_comments = total_comments / num_posts
        avg_engagement = avg_likes + avg_comments
        
        # Engagement rate = (avg engagement per post / followers) * 100
        engagement_rate = (avg_engagement / profile_data['followers']) * 100 if profile_data['followers'] > 0 else 0
        
        return {
            'avg_likes': round(avg_likes, 2),
            'avg_comments': round(avg_comments, 2),
            'avg_total_engagement': round(avg_engagement, 2),
            'engagement_rate': round(engagement_rate, 2)
        }
    
    def _convert_to_number(self, text):
        """Convert Instagram number format (1.2K, 5M) to integer"""
        text = text.replace(',', '').strip()
        
        multipliers = {'K': 1000, 'M': 1000000, 'B': 1000000000}
        
        for suffix, multiplier in multipliers.items():
            if suffix in text.upper():
                number = float(text.upper().replace(suffix, ''))
                return int(number * multiplier)
        
        try:
            return int(float(text))
        except:
            return 0
    
    def _print_report(self, data):
        """Print formatted engagement report"""
        
        print(f"\n📊 Profile Statistics:")
        print(f"   Followers: {data['followers']:,}")
        print(f"   Following: {data['following']:,}")
        print(f"   Total Posts: {data['total_posts']:,}")
        
        print(f"\n💬 Engagement Metrics (based on {data['posts_analyzed']} recent posts):")
        print(f"   Average Likes: {data['avg_likes']:,.2f}")
        print(f"   Average Comments: {data['avg_comments']:,.2f}")
        print(f"   Average Total Engagement: {data['avg_total_engagement']:,.2f}")
        
        print(f"\n📈 Engagement Rate: {data['engagement_rate']:.2f}%")
        
        # Engagement rate interpretation
        if data['engagement_rate'] >= 3:
            rating = "Excellent 🔥"
        elif data['engagement_rate'] >= 1:
            rating = "Good ✅"
        elif data['engagement_rate'] >= 0.5:
            rating = "Average 👍"
        else:
            rating = "Low 📉"
        
        print(f"   Rating: {rating}")
        print(f"\n{'='*60}\n")


# Example usage with CLI arguments
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Instagram engagement scraper (guest/no-login support)')
    parser.add_argument('--username', '-u', type=str, default='jeromepolin', help='Instagram username to analyze')
    parser.add_argument('--guest', action='store_true', help='Run in guest mode (no login). Uses public JSON fallback when needed.')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    args = parser.parse_args()

    scraper = InstagramEngagementScraper(headless=args.headless, guest_mode=args.guest)

    result = scraper.scrape_profile(args.username)

    # Save to JSON
    if result:
        filename = f"{args.username}_engagement.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"✅ Data saved to {filename}")