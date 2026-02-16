"""
Instagram Comments Scraper
Scrapes all comments from a list of Instagram posts using Playwright
Includes username, comment text, likes, timestamp, and reply information
"""

from playwright.sync_api import sync_playwright
import time
import json
from datetime import datetime
import re


class InstagramCommentsScraper:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.playwright = None
        self.browser = None
        self.page = None

    def start(self):
        """Initialize Playwright and browser"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=False)
        self.page = self.browser.new_context().new_page()

    def _is_login_page(self):
        """Detect if we're on Instagram login page"""
        try:
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
                    # Handle: check for incorrect page after click
                    time.sleep(2)
                    error_indicators = [
                        'text=Sorry, your password was incorrect.',
                        'text=checkpoint',
                        'text=Challenge Required',
                        'text=Suspicious Login Attempt',
                        'text=Try again',
                        'text=Enter security code',
                        'text=Please try again later',
                        'text=Too many requests',
                    ]
                    for err_sel in error_indicators:
                        if self.page.query_selector(err_sel):
                            print(f"⚠️ Detected error or checkpoint after login: {err_sel}")
                            return False
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

        # Accept cookies
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

        # Fill in credentials
        try:
            self.page.fill('input[name="email"]', self.username, timeout=5000)
            print(f"✓ Username filled")
        except Exception as e:
            print(f"Error filling username: {e}")

        time.sleep(0.5)

        try:
            self.page.fill('input[name="pass"]', self.password, timeout=5000)
            print(f"✓ Password filled")
        except Exception as e:
            print(f"Error filling password: {e}")

        time.sleep(1)

        # Click login button
        is_login_success = self._click_login_button()
        if not is_login_success:
            print("⚠️ Login button click failed, aborting login flow")
            return False
        time.sleep(5)

        # Dismiss dialogs
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
        return True

    def _scroll_comments_to_end(self, comment_window):
        """Scroll comment window until all comments are loaded"""
        prev_scroll = -1
        max_attempts = 30
        
        for i in range(max_attempts):
            self.page.evaluate('el => el.scrollTop = el.scrollHeight', comment_window)
            time.sleep(1)
            curr_scroll = self.page.evaluate('el => el.scrollTop', comment_window)
            
            if curr_scroll == prev_scroll:
                print(f"✓ Scrolled to bottom of comments after {i+1} attempts")
                return True
            prev_scroll = curr_scroll
        
        print(f"⚠️ Reached max scroll attempts ({max_attempts}) for comments")
        return False

    def _parse_number(self, text):
        """Parse number from text (handles K, M suffixes)"""
        try:
            text = text.strip().split()[0]
            multiplier = 1

            if 'K' in text.upper():
                multiplier = 1000
                text = text.upper().replace('K', '')
            elif 'M' in text.upper():
                multiplier = 1000000
                text = text.upper().replace('M', '')

            number = float(text.replace(',', ''))
            return int(number * multiplier)
        except:
            return 0

    def scrape_post_comments(self, post_url):
        """Scrape all comments from a single Instagram post"""
        print(f"\n{'='*70}")
        print(f"Scraping comments from: {post_url}")
        print(f"{'='*70}")
        
        try:
            self.page.goto(post_url, timeout=60000, wait_until='domcontentloaded')
            time.sleep(3)
        except Exception as e:
            print(f"Error loading post: {e}")
            return []

        comments_data = {
            'username': 'N/A',
            'url': post_url,
            'likes':0,
            'hearts':0,
            'comments': 0,
            'comments_details': []
        }

        comments_detail = []

        try:
            # Find and scroll the comment window
            comment_window = self.page.query_selector('xpath=//*/div/div/div[2]/div/div/div[1]/div[1]/div[2]/section/main/div/div[1]/div/div[2]/div/div[2]')
            
            if comment_window:
                print("✓ Comment window found, scrolling to load all comments...")
                self._scroll_comments_to_end(comment_window)
            else:
                print("⚠️ Comment window not found, attempting to scroll main page")
                self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                time.sleep(2)

            # Extract all comments
            comments_xpath = '//*/div/div/div[2]/div/div/div[1]/div[1]/div[2]/section/main/div/div[1]/div/div[2]/div/div[2]/div/div/div'
            comment_elements = self.page.locator(comments_xpath).all()
            print(f"Found {len(comment_elements)} comment elements")
            comments_data['comments'] = len(comment_elements)
           
             # Extract Username
            username_selectors = [
                'xpath=//div/div/div[1]/div/span/div/span/div/a',  # Collaborator detection path
                'xpath=//div/div/span/span/span/div/a/div/div/span',  # Single posting username detection path
            ]
            
            for selector in username_selectors:
                try:
                    username_elem = self.page.locator(selector).first
                    username_text = username_elem.inner_text(timeout=3000)  # Shorter 3s timeout
                    if username_text and username_text.strip():
                        print(f"✓ Extracted username for comment: {username_text}")
                        comments_data['username'] = username_text.strip()

                        break
                except Exception as selector_err:
                    print(f"✗ Failed to extract username for comment  with {selector}: {str(selector_err)[:60]}")
                    continue

            #extract likes 
            likes_xpath = '//*/div/div/div[2]/div/div/div[1]/div[1]/div[2]/section/main/div/div[1]/div/div[2]/div/div[2]/div/div[2]/div/div/div/div/div/div/div[1]/span/span'
            likes_elements = self.page.locator(likes_xpath).all()   
            print(f"Found {len(likes_elements)} likes elements")
            comments_data['likes'] = len(likes_elements)

            #extract heart
            try:
                heart_likes = self.page.locator('xpath=//div/div/div/section/div[1]/span[2]').inner_text()
                comments_data['hearts'] = self._parse_number(heart_likes)
            except:
                pass
            print(f"✓ Extracted hearts: {comments_data['hearts']}")

            for idx, comment_elem in enumerate(comment_elements, 1):
                try:
                    comment_info = self._extract_comment_data(comment_elem, idx)
                    if comment_info:
                        comments_detail.append(comment_info)
                except Exception as e:
                    print(f"Error extracting comment {idx}: {e}")
                    continue

            comments_data['comments_details'] = comments_detail
            print(f"\n✓ Successfully extracted {len(comments_detail)} comments")
            return comments_data

        except Exception as e:
            print(f"Error scraping post comments: {e}")
            return comments_data

    def _extract_comment_data(self, comment_elem, idx):
        """Extract data from a single comment element"""
        try:
            comment_data = {
                'index': idx,
                'username': 'N/A',
                'text': 'N/A',
            }

            # Extract Username
            username_selectors = [
                'xpath=.//div[1]/span[1]/span',  # Relative xpath to link
            ]
            
            for selector in username_selectors:
                try:
                    username_elem = comment_elem.locator(selector).first
                    username_text = username_elem.inner_text(timeout=3000)  # Shorter 3s timeout
                    if username_text and username_text.strip():
                        print(f"✓ Extracted username for comment {idx}: {username_text}")
                        comment_data['username'] = username_text.strip()

                        break
                except Exception as selector_err:
                    print(f"✗ Failed to extract username for comment {idx} with {selector}: {str(selector_err)[:60]}")
                    continue
            
            # Extract Comment Text
            text_selectors = [
                'xpath=.//div/div[2]/span',  # Relative xpath to comment text
                'xpath=.//div/span/div/span',  # Alternative path for text
            ]
            
            for selector in text_selectors:
                try:
                    text_elem = comment_elem.locator(selector).first
                    text_content = text_elem.inner_text(timeout=3000)
                    if text_content and text_content.strip():
                        print(f"✓ Extracted comment text for comment {idx}: {text_content[:100]}...")
                        comment_data['text'] = text_content.strip()
                        break
                except Exception as selector_err:
                    print(f"✗ Failed to extract comment text for comment {idx} with {selector}: {str(selector_err)[:60]}")
                    continue

            return comment_data

        except Exception as e:
            print(f"Error extracting comment data: {e}")
            return None

    def scrape_posts_comments(self, post_urls):
        """Scrape comments from multiple posts"""
        # all_comments = {}
        results = []
        for idx, post_url in enumerate(post_urls, 1):
            print(f"\n[{idx}/{len(post_urls)}] Processing post...")
            
            # Ensure URL is complete
            if not post_url.startswith('http'):
                post_url = f"https://www.instagram.com{post_url}"

            comments = self.scrape_post_comments(post_url)
            # all_comments[post_url] = comments
            results.append(comments)
            time.sleep(2)  # Delay between posts

        return results

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
    USERNAME = "XXX"
    PASSWORD = "YYY"

    # List of post URLs to scrape comments from
    POST_URLS = [
        "https://www.instagram.com/reel/DUrdSKuEgfL/?igsh=bHg4M3c2Y3ExaG84",
        "https://www.instagram.com/reel/DUsbiyZEvMs/?igsh=Z3hhNHhnMmYyMjhr",         
    ]

    # Initialize scraper
    scraper = InstagramCommentsScraper(USERNAME, PASSWORD)

    try:
        # Start browser
        scraper.start()

        # Login
        if not scraper.login():
            print("Login failed, exiting...")
            return

        # Scrape comments from posts
        all_comments = scraper.scrape_posts_comments(POST_URLS)

        # Save results to JSON
        output = {
            'total_posts': len(POST_URLS),
            'scraped_at': datetime.now().isoformat(),
            'posts_comments': all_comments,
        }

        filename = f'./output_comments/instagram_comments_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Data saved to {filename}")

        # Print summary
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        # for post_url, comments in all_comments.items():
        #     print(f"\nPost: {post_url}")
        #     print(f"  Comments extracted: {len(comments)}")
        #     if comments:
        #         total_likes = sum(c.get('likes', 0) for c in comments)
        #         print(f"  Total comment likes: {total_likes}")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        # Close browser
        scraper.close()


if __name__ == "__main__":
    main()
