"""
Instagram Profile and Posts Scraper with Engagement Rate Calculator
Uses Playwright for web automation
"""

from playwright.sync_api import sync_playwright
import time
import json
from datetime import datetime

class InstagramScraper:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.playwright = None
        self.browser = None
        self.page = None

    def start(self):
        """Initialize Playwright and browser"""
        self.playwright = sync_playwright().start()
        # Use chromium with headless=False to see the browser (set True for background)
        self.browser = self.playwright.chromium.launch(headless=False)
        self.page = self.browser.new_context().new_page()

    def _is_login_page(self):
        """Detect if we're on Instagram login page"""
        try:
            # Check for login page indicators
            login_indicators = [
                'input[name="email"]',
                'input[name="pass"]',
            ]
            
            for indicator in login_indicators:
                if self.page.query_selector(indicator):
                    print(f"✓ Login page detected (found: {indicator})")
                    return True
            return False
        except Exception as e:
            print(f"Error detecting login page: {e}")
            return False

    def _click_login_button(self, timeout=10000):
        """Try multiple XPath selectors to click the login button"""
        button_selectors = [
            "xpath=//*[@id='login_form']/div/div[1]/div/div[3]/div/div/div",
        ]
        
        for selector in button_selectors:
            try:
                print(f"Attempting: {selector}")
                element = self.page.query_selector(selector)
                if element:
                    self.page.click(selector, timeout=timeout)
                    print(f"✓ Clicked login button with: {selector}")
                    return True
            except Exception as e:
                print(f"✗ Failed with {selector}: {str(e)[:60]}")
                continue
        
        print("⚠️ Could not find login button")
        return False

    def login(self):
        """Login to Instagram with credentials"""
        print("Navigating to Instagram login...")
        try:
            self.page.goto('https://www.instagram.com/accounts/login/', timeout=60000, wait_until='domcontentloaded')
            time.sleep(2)
        except Exception as e:
            print(f"Error navigating to login page: {e}")
            return False

        # Wait and verify we're on login page
        max_wait = 10
        for i in range(max_wait):
            if self._is_login_page():
                print("✓ Successfully loaded login page")
                break
            if i < max_wait - 1:
                print(f"⏳ Waiting for login page... ({i+1}/{max_wait})")
                time.sleep(1)
            else:
                print("⚠️ Login page did not load within timeout")

        time.sleep(1)

        # Accept cookies if prompt appears
        try:
            cookie_buttons = [
                'button:has-text("Allow all cookies")',
                'button:has-text("Allow All")',
                'button:has-text("Accept")',
            ]
            for btn_selector in cookie_buttons:
                try:
                    self.page.click(btn_selector, timeout=3000)
                    print("✓ Cookies accepted")
                    break
                except:
                    continue
        except Exception as e:
            print(f"⚠️ Cookie dialog skipped: {e}")

        time.sleep(1)

        # Fill in username
        try:
            username_selectors = [
                'input[name="email"]',
            ]
            for sel in username_selectors:
                try:
                    self.page.fill(sel, self.username, timeout=5000)
                    print(f"✓ Username filled using: {sel}")
                    break
                except:
                    continue
        except Exception as e:
            print(f"Error filling username: {e}")

        time.sleep(0.5)

        # Fill in password
        try:
            password_selectors = [
                'input[name="pass"]',
            ]
            for sel in password_selectors:
                try:
                    self.page.fill(sel, self.password, timeout=5000)
                    print(f"✓ Password filled using: {sel}")
                    break
                except:
                    continue
        except Exception as e:
            print(f"Error filling password: {e}")

        time.sleep(1)

        # Click login button
        is_login_success = self._click_login_button()
        if(not is_login_success):
            print("⚠️ Login button click failed, aborting login flow")
            return
        time.sleep(5)

        # Handle "Save login info" prompt
        try:
            save_buttons = [
                'button:has-text("Not now")',
                'button:has-text("Not Now")',
                'button:has-text("Save Info")',
            ]
            for btn in save_buttons:
                try:
                    self.page.click(btn, timeout=3000)
                    print("✓ 'Save login info' dismissed")
                    break
                except:
                    continue
        except:
            pass

        time.sleep(1)

        # Handle "Turn on notifications" prompt
        try:
            notif_buttons = [
                'button:has-text("Not Now")',
                'button:has-text("Not now")',
                'button:has-text("Turn Off")',
            ]
            for btn in notif_buttons:
                try:
                    self.page.click(btn, timeout=3000)
                    print("✓ Notifications prompt dismissed")
                    break
                except:
                    continue
        except:
            pass

        print("✓ Login flow completed")

    def scrape_profile(self, profile_username):
        """Scrape profile information"""
        print(f"Scraping profile: {profile_username}")
        self.page.goto(f'https://www.instagram.com/{profile_username}/')
        time.sleep(3)

        profile_data = {}

        try:
            # Get profile name
            profile_data['username'] = profile_username

            # Get full name
            try:
                profile_data['full_name'] = self.page.locator('section header h2').inner_text()
            except:
                profile_data['full_name'] = 'N/A'
            print(f"Full name: {profile_data['full_name']}")
            # Get stats (posts, followers, following)
            stats = self.page.locator('section ul li').all_text_contents()
            print(f"Profile stats raw: {stats}")

            # Parse stats
            for stat in stats[:3]:
                if 'post' in stat.lower():
                    profile_data['posts_count'] = self._parse_number(stat)
                elif 'follower' in stat.lower():
                    profile_data['followers'] = self._parse_number(stat)
                elif 'following' in stat.lower():
                    profile_data['following'] = self._parse_number(stat)

            # Get bio
            try:
                profile_data['bio'] = self.page.locator('section div._aa_c h1').inner_text()
            except:
                profile_data['bio'] = 'N/A'

            print(f"Profile data: {json.dumps(profile_data, indent=2)}")
            return profile_data

        except Exception as e:
            print(f"Error scraping profile: {e}")
            return profile_data

    def scrape_posts(self, profile_username, num_posts=12):
        """Scrape posts from profile"""
        print(f"Scraping posts from: {profile_username}")

        posts_data = []

        try:
            # Get all post links
            self.page.goto(f'https://www.instagram.com/{profile_username}/')
            time.sleep(3)

            # Scroll to load posts
            for _ in range(1):
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(2)

            # Get post links
            post_links = self.page.locator('xpath=//*/div/div/div[2]/div/div/div[1]/div[2]/div[2]/section/main/div/div/div[2]/div/div/div/div/div/div/a').all()
            post_urls = [link.get_attribute('href') for link in post_links[:num_posts]]

            print(f"Found {len(post_urls)} posts to scrape")
            time.sleep(10)
            # Visit each post and get details
            for idx, post_url in enumerate(post_urls, 1):
                print(f"Scraping post {idx}/{len(post_urls)}")
                full_url = f"https://www.instagram.com{post_url}"

                post_data = self._scrape_single_post(full_url)
                posts_data.append(post_data)

                time.sleep(2)
                break
            return posts_data

        except Exception as e:
            print(f"Error scraping posts: {e}")
            return posts_data

    def _scrape_single_post(self, post_url):
        """Scrape single post details"""
        self.page.goto(post_url)
        print('='*40)
        print(f"Scraping post: {post_url}")
        time.sleep(3)

        # Scroll to bottom of comment window if present
        try:
            # Find the comment window element (Instagram uses a div with role="dialog" or similar)
            comment_window = self.page.query_selector('xpath=//*/div/div/div[2]/div/div/div[1]/div[1]/div[2]/section/main/div/div[1]/div/div[2]/div/div[2]')
            if comment_window:
                max_attempts = 20
                for i in range(max_attempts):
                    val1 = self.page.evaluate('el => el.scrollTop = el.scrollHeight', comment_window)
                    time.sleep(3)
                    curr_scroll = self.page.evaluate('el => el.scrollHeight', comment_window)
                    if val1 == curr_scroll:
                        print(f"✓ Scrolled to bottom of comment window after {i+1} attempts")
                        break
                else:
                    print(f"⚠️ Reached max scroll attempts ({max_attempts}) in comment window")
                self.page.evaluate('el => el.scrollTop', comment_window)
            else:
                # Fallback: scroll main page
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                print("✓ Scrolled to bottom of main page")
        except Exception as e:
            print(f"⚠️ Could not scroll comment window: {e}")
        post_data = {
            'url': post_url,
            'likes': 0,
            'comments': 0,
            'caption': '',
            'timestamp': ''
        }



        try:
            # Get likes count for each comment
            try:
                raw_likes_on_comments = self.page.locator("xpath=//*/div/div/div[2]/div/div/div[1]/div[1]/div[2]/section/main/div/div[1]/div/div[2]/div/div[2]/div/div[2]/div/div/div/div[2]/div[1]/div/div/span/span[contains(text(), 'likes')]")
                likes_onComments = []
                for text in raw_likes_on_comments.all():
                    text_content = text.text_content()
                    count = self._parse_number(text_content)
                    if 'K' in text_content.replace("likes", "").strip().upper():
                        likes_onComments.append(count * 1000)
                    elif 'M' in text_content.replace("likes", "").strip().upper():
                        likes_onComments.append(count * 1000000)
                    else:
                        likes_onComments.append(count)
                print(likes_onComments)
                post_data['likes'] = sum(likes_onComments) if likes_onComments else 0
            except:
                pass

            # Get comments count
            try:
                comments = self.page.locator('ul li div[role="button"]').all()
                post_data['comments'] = len(comments)
            except:
                pass

            # Get caption
            try:
                caption = self.page.locator('h1').inner_text()
                post_data['caption'] = caption[:100]  # First 100 chars
            except:
                pass

            # Get timestamp
            try:
                timestamp = self.page.locator('time').get_attribute('datetime')
                post_data['timestamp'] = timestamp
            except:
                pass

        except Exception as e:
            print(f"Error scraping post details: {e}")

        return post_data

    def calculate_engagement_rate(self, post_data, followers_count):
        """Calculate engagement rate for a single post"""
        total_engagement = post_data['likes'] + post_data['comments']

        if followers_count > 0:
            engagement_rate = (total_engagement / followers_count) * 100
        else:
            engagement_rate = 0

        return round(engagement_rate, 2)

    def calculate_average_engagement(self, posts_data, followers_count):
        """Calculate average engagement rate across all posts"""
        if not posts_data or followers_count == 0:
            return 0

        total_engagement_rate = 0
        valid_posts = 0

        for post in posts_data:
            engagement_rate = self.calculate_engagement_rate(post, followers_count)
            total_engagement_rate += engagement_rate
            valid_posts += 1

        avg_engagement = total_engagement_rate / valid_posts if valid_posts > 0 else 0
        return round(avg_engagement, 2)

    def _parse_number(self, text):
        """Parse number from text (handles K, M suffixes)"""
        text = text.strip().split()[0]
        multiplier = 1

        if 'K' in text.upper():
            multiplier = 1000
            text = text.upper().replace('K', '')
        elif 'M' in text.upper():
            multiplier = 1000000
            text = text.upper().replace('M', '')

        try:
            number = float(text.replace(',', ''))
            return int(number * multiplier)
        except:
            return 0

    def close(self):
        """Close browser and playwright"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        print("Browser closed")


# Example usage
def main():
    # Your Instagram credentials
    USERNAME = ""
    PASSWORD = ""

    # Profile to scrape
    TARGET_PROFILE = "jeromepolin"  # Example: National Geographic
    NUM_POSTS = 12  # Number of posts to scrape

    # Initialize scraper
    scraper = InstagramScraper(USERNAME, PASSWORD)

    try:
        # Start browser
        scraper.start()

        # Step 1: Login
        scraper.login()

        # Step 2: Scrape profile
        profile_data = scraper.scrape_profile(TARGET_PROFILE)

        # Step 3: Scrape posts
        posts_data = scraper.scrape_posts(TARGET_PROFILE, NUM_POSTS)

        # Get followers count for engagement calculation
        followers_count = profile_data.get('followers', 0)

        # Step 4: Calculate engagement rate for each post
        print("\n" + "="*50)
        print("ENGAGEMENT RATES PER POST")
        print("="*50)

        for idx, post in enumerate(posts_data, 1):
            engagement_rate = scraper.calculate_engagement_rate(post, followers_count)
            post['engagement_rate'] = engagement_rate

            print(f"\nPost {idx}:")
            print(f"  URL: {post['url']}")
            print(f"  Likes: {post['likes']:,}")
            print(f"  Comments: {post['comments']:,}")
            print(f"  Engagement Rate: {engagement_rate}%")

        # Step 5: Calculate average engagement rate
        avg_engagement = scraper.calculate_average_engagement(posts_data, followers_count)

        print("\n" + "="*50)
        print("SUMMARY")
        print("="*50)
        print(f"Profile: @{TARGET_PROFILE}")
        print(f"Followers: {followers_count:,}")
        print(f"Posts Analyzed: {len(posts_data)}")
        print(f"Average Engagement Rate: {avg_engagement}%")
        print("="*50)

        # Save to JSON file
        output = {
            'profile': profile_data,
            'posts': posts_data,
            'average_engagement_rate': avg_engagement,
            'scraped_at': datetime.now().isoformat()
        }

        with open(f'{TARGET_PROFILE}_data.json', 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\nData saved to {TARGET_PROFILE}_data.json")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        # Close browser
        scraper.close()


if __name__ == "__main__":
    main()

