import os
from pathlib import Path
from datetime import datetime
import gradio as gr
from github import Github, Auth, GithubException
from git import Repo, Actor
import json
from slugify import slugify
from dotenv import load_dotenv, set_key

# --- Configuration ---
HUGO_PROJECT_PATH = Path("/project/developer-portal-fork-test")
CONTENT_AUTHORS_PATH = HUGO_PROJECT_PATH / "content/authors"
DATA_AUTHORS_PATH = HUGO_PROJECT_PATH / "data/authors"
CONTENT_BLOG_PATH = HUGO_PROJECT_PATH / "content/blog"
CLONE_PATH = HUGO_PROJECT_PATH
CODE_SERVER_BASE = "http://localhost:8087/"
REPO_FULL_NAME = "espressif/developer-portal"

# Ensure directories exist
for path in [CONTENT_AUTHORS_PATH, DATA_AUTHORS_PATH, CONTENT_BLOG_PATH]:
    path.mkdir(parents=True, exist_ok=True)

# --- Helper Functions ---
def list_authors():
    return sorted([p.name for p in CONTENT_AUTHORS_PATH.iterdir() if p.is_dir()])

def format_author_name(name: str):
    return name.strip().replace(" ", "-").lower()

def get_project_repo_name():
    """Get the name of the repository inside /project folder."""
    project_path = Path("/project")
    if not project_path.exists():
        return "developer-portal-fork-test"  # fallback
    
    # List all directories in /project
    repo_dirs = [d for d in project_path.iterdir() if d.is_dir()]
    
    if len(repo_dirs) == 1:
        # If there's exactly one directory, use its name
        return repo_dirs[0].name
    elif len(repo_dirs) > 1:
        # If multiple directories, try to find one that looks like a git repo
        for repo_dir in repo_dirs:
            if (repo_dir / ".git").exists():
                return repo_dir.name
        # If no git repo found, use the first directory
        return repo_dirs[0].name
    else:
        # No directories found
        return "developer-portal-fork-test"  # fallback

# --- Author Functions ---
def create_author(name):
    if not name or not name.strip():
        return "❌ Please enter a valid author name.", gr.update(), gr.update()
    
    name_formatted = format_author_name(name)
    author_dir = CONTENT_AUTHORS_PATH / name_formatted
    author_dir.mkdir(parents=True, exist_ok=True)
    
    (author_dir / "_index.md").write_text(f"---\ntitle: {name_formatted}\n---\n")
    (DATA_AUTHORS_PATH / f"{name_formatted}.json").write_text(
        json.dumps({"name": name_formatted, "bio": "", "image": ""}, indent=2)
    )
    
    authors = list_authors()
    status_msg = f"✅ Author '{name_formatted}' created! ({len(authors)} total)"
    update_choices = gr.update(choices=authors, value=name_formatted)
    return status_msg, update_choices, update_choices

def refresh_authors(default_author="espressif"):
    authors = list_authors()
    status_msg = f"🔄 Refreshed! ({len(authors)} authors)"
    # Use default_author if exists, else first author
    value = default_author if default_author in authors else (authors[0] if authors else None)
    update_choices = gr.update(choices=authors, value=value)
    return status_msg, update_choices, update_choices


# --- Article Function ---
def create_article(title, author_name, pat, email, terminal):
    terminal += "Starting create_article\n"
    if not pat:
        load_dotenv(override=True)
        pat = os.getenv('GITHUB_PAT')
        if not pat:
            terminal += "No PAT found\n"
            return "❌ No PAT provided in UI or .env", gr.update(), gr.update(visible=False), gr.update(visible=False), terminal
    
    if not title or not author_name:
        terminal += "Missing title or author\n"
        return "❌ Please provide both title and author.", gr.update(), gr.update(visible=False), gr.update(visible=False), terminal
    
    # Handle email
    if email:
        commit_email = email
        set_key('.env', 'USER_EMAIL', email)
        terminal += f"Using email from UI: {email}\n"
    else:
        load_dotenv(override=True)
        commit_email = os.getenv('USER_EMAIL')
        if not commit_email:
            terminal += "No email found\n"
            return "❌ No email provided in UI or .env", gr.update(), gr.update(visible=False), gr.update(visible=False), terminal
        terminal += f"Using email from .env: {commit_email}\n"
    
    now = datetime.now()
    y, m = now.strftime("%Y"), now.strftime("%m")
    article_slug = slugify(title)
    article_dir = CONTENT_BLOG_PATH / y / m / article_slug
    article_dir.mkdir(parents=True, exist_ok=True)
    set_key('.env', 'ARTICLE_FOLDER', str(article_dir))  # Add ARTICLE_FOLDER to .env
    set_key('.env', 'ARTICLE_TITLE', title)  # Add ARTICLE_TITLE to .env
    terminal += f"Created article dir: {article_dir}\n"
    
    # Format date as YYYY-MM-DD only
    date_only = now.strftime("%Y-%m-%d")
    
    author_formatted = format_author_name(author_name)
    
    (article_dir / "index.md").write_text(f"""---
title: "{title}"
date: "{date_only}"
summary: "This article explains many useful things."
authors:
  - "{author_formatted}"
tags: ["ESP-IDF"]
---
""")
    terminal += "Wrote index.md\n"
    
    # Create branch and add file
    #try:
    repo = clone_or_open_repo(pat)
    g = Github(auth=Auth.Token(pat))
    user = g.get_user()
    author_actor = Actor(user.login, commit_email or user.email or f"{user.login}@users.noreply.github.com")
    repo.git.checkout('main')
    branch_name = f"article/{slugify(title, separator='_')}"
    repo.git.checkout('HEAD', b=branch_name)
    repo.git.add(str(article_dir))
    repo.git.add(str(DATA_AUTHORS_PATH))
    repo.git.add(str(CONTENT_AUTHORS_PATH))
    repo.index.commit(f"{title} first commit", author=author_actor)
    terminal += f"Created branch {branch_name} and committed\n"
    #except Exception as e:
     #   print(f"Error creating branch and committing article: {e}")
    
    # Get repository name from /project folder
    repo_name = get_project_repo_name()
    terminal += f"Detected repo name: {repo_name}\n"
    
    vscode_link = f"{CODE_SERVER_BASE}?folder=/project/{repo_name}/content/blog/{y}/{m}/{article_slug}"
    preview_link = f"http://localhost:1313/blog/{y}/{m}/{article_slug}/"
    
    # Generate branch name for UI
    ui_branch_name = f"add/{article_slug}"
    
    # Return separate status message and VS Code link with styling
    status_msg = f"✅ Article '{title}' created by {author_name}."
    
    # Create styled link with chain emoji - red theme
    vscode_msg = f"""
    <div style="
        background: linear-gradient(135deg, #f56565 0%, #c53030 100%);
        padding: 12px 20px;
        border-radius: 8px;
        margin: 10px 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border: 2px solid #742a2a;
    ">
        <a href="{vscode_link}" target="_blank" style="
            color: white;
            text-decoration: none;
            font-weight: bold;
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        ">
            🔗 Open in VS Code
        </a>
    </div>
    """
    
    # Create styled preview link - orange theme
    preview_msg = f"""
    <div style="
        background: linear-gradient(135deg, #ed8936 0%, #dd6b20 100%);
        padding: 12px 20px;
        border-radius: 8px;
        margin: 10px 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border: 2px solid #c05621;
    ">
        <a href="{preview_link}" target="_blank" style="
            color: white;
            text-decoration: none;
            font-weight: bold;
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        ">
            👁️ Preview Article
        </a>
    </div>
    """
    
    return status_msg, gr.update(value=ui_branch_name), vscode_msg, preview_msg, terminal

# --- Git Functions ---
def check_git_credentials(pat, email, terminal):
    if email:
        set_key('.env', 'USER_EMAIL', email)
        terminal += f"Saved email to .env: {email}\n"
    
    if not pat:
        load_dotenv(override=True)
        pat = os.getenv('GITHUB_PAT')
        if not pat:
            terminal += "No PAT in UI or .env\n"
            return "❌ No PAT provided in UI or .env", "", "", terminal
    else:
        set_key('.env', 'GITHUB_PAT', pat)
        terminal += "Saved PAT to .env\n"
    
    terminal += f"Read PAT: {pat}\n"
    try:
        g = Github(auth=Auth.Token(pat))
        user = g.get_user()
        username = user.login
        terminal += f"Authenticated as: {username}\n"
        
        # Extract repo full name from local repo if cloned
        if CLONE_PATH.exists():
            repo = Repo(CLONE_PATH)
            remote_url = repo.remote("origin").url
            parts = remote_url.rstrip('/').split('/')
            owner = parts[-2]
            repo_name = parts[-1].replace('.git', '')
            repo_full_name = f"{owner}/{repo_name}"
        else:
            repo_full_name = REPO_FULL_NAME  # Fallback if not cloned
        
        repo = g.get_repo(repo_full_name)
        permissions = repo.get_collaborator_permission(user.login)
        if permissions in ['admin', 'write']:
            status_msg = "✅ Credentials valid: Push and branch creation allowed."
        else:
            status_msg = "❌ Credentials valid but push and branch creation not allowed."
        terminal += f"Repo: {repo_full_name}, Permissions: {permissions}\n"
        return status_msg, repo_full_name, username, terminal
    except GithubException as e:
        if e.status == 403:
            terminal += f"403 error: {e}\n"
            return "❌ Credentials valid but push and branch creation not allowed.", "", username, terminal
        else:
            terminal += f"GitHub error: {e}\n"
            return f"❌ Check failed: {str(e)}", "", "", terminal
    except Exception as e:
        terminal += f"General error: {e}\n"
        return f"❌ Check failed: {str(e)}", "", "", terminal

def fork_repo(pat):
    try:
        g = Github(auth=Auth.Token(pat))
        user = g.get_user()
        username = user.login
        
        # Get today's date in YYYY-MM-DD format
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Create custom fork name
        fork_name = f"developer_portal_{username}_{today}"
        
        # Get the original repo
        original_repo = g.get_repo(REPO_FULL_NAME)
        
        # Check if fork already exists with this name
        existing_fork = None
        for repo in user.get_repos():
            if repo.name == fork_name and repo.fork:
                existing_fork = repo
                break
        
        if existing_fork:
            fork = existing_fork
            status_msg = f"✅ Using existing fork: {fork.full_name}"
        else:
            # Create fork with custom name
            fork = user.create_fork(original_repo, name=fork_name)
            status_msg = f"✅ Created new fork: {fork.full_name}"
        
        # Clone the forked repo with recursive shallow submodules
        if CLONE_PATH.exists():
            # Remove existing clone if it exists
            import shutil
            shutil.rmtree(CLONE_PATH)
        
        # Clone with recursive and shallow-submodules
        import subprocess
        clone_cmd = ["git", "clone", "--recursive", "--shallow-submodules", fork.ssh_url, str(CLONE_PATH)]
        result = subprocess.run(clone_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return f"❌ Clone failed: {result.stderr}"
        
        return f"{status_msg}\n✅ Cloned to {CLONE_PATH} with recursive shallow submodules"
        
    except Exception as e:
        return f"❌ Fork failed: {str(e)}"

def clone_or_open_repo(pat):
    if CLONE_PATH.exists():
        return Repo(CLONE_PATH)
    g = Github(auth=Auth.Token(pat))
    user = g.get_user()
    repo_g = g.get_repo(REPO_FULL_NAME)
    fork = next((f for f in user.get_repos() if f.full_name.endswith(repo_g.name)), None)
    if not fork:
        fork = user.create_fork(repo_g)
    Repo.clone_from(fork.ssh_url, CLONE_PATH)
    return Repo(CLONE_PATH)

def create_branch(branch_name, pat):
    try:
        repo = clone_or_open_repo(pat)
        repo.git.checkout('main')
        repo.git.checkout('HEAD', b=branch_name)
        return f"✅ Branch '{branch_name}' created."
    except Exception as e:
        return f"❌ Branch failed: {str(e)}"

def commit_changes(message, pat, terminal):
    print("Commit start")
    try:
        repo = clone_or_open_repo(pat)
        load_dotenv(override=True)
        article_folder = os.getenv('ARTICLE_FOLDER')
        print(article_folder)
        terminal += f"Article folder: {article_folder}\n"
        if not article_folder or not os.path.exists(article_folder):
            terminal += "Article folder does not exist\n"
            return "❌ Article folder does not exist", terminal
        repo.git.add(article_folder)
        repo.git.add(str(DATA_AUTHORS_PATH))
        repo.git.add(str(CONTENT_AUTHORS_PATH))
        repo.index.commit(message)
        terminal += f"Committed: {message}\n"
        return f"✅ Committed: '{message}'", terminal
    except Exception as e:
        terminal += f"Commit error: {e}\n"
        return f"❌ Commit failed: {str(e)}", terminal

def push_changes(branch_name, pat, message, terminal):
    try:
        repo = clone_or_open_repo(pat)
        load_dotenv(override=True)
        title = os.getenv('ARTICLE_TITLE', 'article')
        branch_name = repo.active_branch.name
        repo.index.commit(f"added {title}")
        origin = repo.remote(name='origin')
        origin.push(refspec=f"{branch_name}:{branch_name}")
        terminal += f"Pushed branch: {branch_name}\n"
        return f"✅ Committed and pushed '{branch_name}'", terminal
    except Exception as e:
        terminal += f"Push error: {e}\n"
        return f"❌ Push failed: {str(e)}", terminal

def create_pr(title):
    return f"Dummy PR '{title}' created"

# --- Gradio UI ---
with gr.Blocks(title="Developer portal article manager", css="""
    .vscode-link-container {
        margin: 10px 0;
        padding: 12px 20px;
        background: linear-gradient(135deg, #f56565 0%, #c53030 100%);
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border: 2px solid #742a2a;
    }
    .vscode-link {
        color: white !important;
        text-decoration: none !important;
        font-weight: bold !important;
        font-size: 16px !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
    }
    .vscode-link:hover {
        color: #fed7d7 !important;
        text-decoration: underline !important;
    }
    .preview-link-container {
        margin: 10px 0;
        padding: 12px 20px;
        background: linear-gradient(135deg, #ed8936 0%, #dd6b20 100%);
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border: 2px solid #c05621;
    }
    .preview-link {
        color: white !important;
        text-decoration: none !important;
        font-weight: bold !important;
        font-weight: bold !important;
        font-size: 16px !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
    }
    .preview-link:hover {
        color: #feebc8 !important;
        text-decoration: underline !important;
    }
""") as demo:
    terminal_state = gr.State("")
    with gr.Accordion("Logs"):
        # Status outputs
        author_status = gr.Markdown()
        article_output = gr.Markdown()
        git_output = gr.Markdown()
    with gr.Row():
        vscode_link_output = gr.HTML()
        preview_link_output = gr.HTML()
    with gr.Tabs():
        with gr.TabItem("Git Credentials"):
            with gr.Row():
                pat_tb = gr.Textbox(label="GitHub PAT", type="password")
                email_tb = gr.Textbox(label="Commit Email", placeholder="user@example.com")
            with gr.Row(): 
                repo_display_tb = gr.Textbox(label="Detected Repo Name", interactive=False)
                username_tb = gr.Textbox(label="Detected Username", interactive=False)
            with gr.Row():
                gr.Button("🔍 Check Git").click(check_git_credentials, [pat_tb, email_tb, terminal_state], [git_output, repo_display_tb, username_tb, terminal_state])
                gr.Button("🍴 Fork Developer Portal", interactive=False).click(fork_repo, [pat_tb], [git_output])
        
        with gr.TabItem("Author"):
            author_choice = gr.Radio(
                label="Author Option",
                choices=["Use existing author", "Create new author"],
                value="Use existing author"
            )
            # Existing Author Section
            with gr.Accordion("Existing Author", open=True, visible=True) as existing_accordion:
                existing_author_dd = gr.Dropdown(label="Select Author", choices=[], interactive=True)
            
            # New Author Section
            with gr.Accordion("New Author", open=False, visible=False) as new_accordion:
                with gr.Row():
                    with gr.Column(scale=2):
                        new_author_tb = gr.Textbox(label="New Author Name", placeholder="New author...")
                        create_author_btn = gr.Button("➕ Create Author", variant="primary")
        
        with gr.TabItem("Article"):
            # Article Section
            article_title_tb = gr.Textbox(label="Article Title", placeholder="My first post...")
            create_article_btn = gr.Button("📝 Create Article", variant="stop")

        
        with gr.TabItem("Edit Operations"):
            
            branch_tb = gr.Textbox(label="Branch", placeholder="feature/blog", interactive=False)
            msg_tb = gr.Textbox(label="Commit Msg", value="Add authors/articles")
            with gr.Row():
                gr.Button("💾 Commit").click(commit_changes, [msg_tb, pat_tb, terminal_state], [git_output, terminal_state])
                gr.Button("⬆️ Push", variant="stop", interactive=False).click(push_changes, [branch_tb, pat_tb, msg_tb, terminal_state], [git_output, terminal_state])
        
        with gr.TabItem("Publishing Operations"):
            pr_title_tb = gr.Textbox(label="Pull Request Title", placeholder="Enter PR title...")
            pr_descripton_tb=gr.Textbox(label="Description", lines=10, max_lines=20)  # Scrollable textarea
            gr.Button("🔀 Create Pull Request", variant="primary", interactive=False).click(create_pr, inputs=[pr_title_tb], outputs=[git_output])
    

        
    

    # Connect buttons to functions
    create_author_btn.click(
        create_author,
        inputs=[new_author_tb],
        outputs=[author_status, existing_author_dd, existing_author_dd]
    )
    
    # refresh_btn.click(
    #     refresh_authors,
    #     inputs=None,
    #     outputs=[author_status, existing_author_dd, existing_author_dd]
    # )
    
    create_article_btn.click(
        create_article, 
        inputs=[article_title_tb, existing_author_dd, pat_tb, email_tb, terminal_state], 
        outputs=[article_output, branch_tb, vscode_link_output, preview_link_output, terminal_state]
    )

    def startup():
        # Load authors
        status, dd1, dd2 = refresh_authors("espressif")
        
        # Load .env
        load_dotenv(override=True)
        pat = os.getenv('GITHUB_PAT')
        email = os.getenv('USER_EMAIL')
        
        git_msg = ""
        if pat:
            git_msg += "✅ Found GITHUB_PAT in .env\n"
        if email:
            git_msg += "✅ Found USER_EMAIL in .env\n"
        
        return status, dd1, dd2, gr.update(value=pat or ""), gr.update(value=email or ""), gr.update(value=git_msg)

    # ✅ Populate dropdown at startup
    demo.load(
        startup,
        inputs=[],
        outputs=[author_status, existing_author_dd, existing_author_dd, pat_tb, email_tb, git_output]
    )

    def toggle_accordions(choice):
        if choice == "Use existing author":
            return gr.update(visible=True), gr.update(visible=False)
        else:
            return gr.update(visible=False), gr.update(visible=True)

    author_choice.change(
        toggle_accordions,
        inputs=[author_choice],
        outputs=[existing_accordion, new_accordion]
    )

demo.launch(server_name="0.0.0.0", server_port=7860, debug=True)
