# Deployment

## 1. Publish the code on GitHub

Recommended repository name:

```text
ksu-marietta-parking-optimizer
```

### GitHub web upload

1. Create a new **public** repository on GitHub.
2. Do not add a generated README or `.gitignore` during repository creation; this project already contains both.
3. Extract the GitHub-ready ZIP locally.
4. Upload the **contents** of the `ksu-marietta-parking-optimizer` folder to the repository root.
5. Commit the upload to `main`.

### Git command line alternative

From inside this project folder:

```bash
git init
git add .
git commit -m "Initial public release"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ksu-marietta-parking-optimizer.git
git push -u origin main
```

## 2. Deploy the live demo with Streamlit Community Cloud

1. Sign in to Streamlit Community Cloud with access to the GitHub repository.
2. Create a new app.
3. Choose the `ksu-marietta-parking-optimizer` repository and the `main` branch.
4. Set the main file path to:

```text
app.py
```

5. Deploy the app.

The current MVP does not require API keys, a database, or other secrets.

## 3. After deployment

Once the public app URL exists, add it near the top of `README.md`, for example:

```markdown
**Live demo:** https://your-app-name.streamlit.app
```

Then commit and push that README change so portfolio reviewers can move directly between the source code and the live application.
