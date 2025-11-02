# PyPI Trusted Publishing Setup

This project uses GitHub Actions with PyPI's Trusted Publishing (OpenID Connect) for secure, automated releases. No API tokens needed!

## How It Works

The workflow automatically publishes to PyPI when you create a GitHub release. It uses OIDC authentication which is more secure than API tokens.

**Workflow triggers:**
- ✅ **GitHub Release (published)** → Publishes to PyPI
- ✅ **Tag push (`v*`)** → Publishes to TestPyPI
- ✅ **Manual workflow dispatch** → Choose PyPI or TestPyPI

## One-Time PyPI Setup

You need to configure Trusted Publishing on PyPI **before** the first release.

### Step 1: Create PyPI Account

1. Go to https://pypi.org/account/register/
2. Create account and verify email
3. Enable 2FA (required for publishing)

### Step 2: Configure Trusted Publishing on PyPI

1. Go to https://pypi.org/manage/account/publishing/
2. Click "Add a new pending publisher"
3. Fill in the form:
   - **PyPI Project Name:** `ace-skyspark-lib`
   - **Owner:** `ACE-IoT-Solutions`
   - **Repository name:** `ace-skyspark-lib`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
4. Click "Add"

### Step 3: Configure Trusted Publishing on TestPyPI (Optional but Recommended)

1. Create account at https://test.pypi.org/account/register/
2. Go to https://test.pypi.org/manage/account/publishing/
3. Click "Add a new pending publisher"
4. Fill in the form:
   - **PyPI Project Name:** `ace-skyspark-lib`
   - **Owner:** `ACE-IoT-Solutions`
   - **Repository name:** `ace-skyspark-lib`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `testpypi`
5. Click "Add"

### Step 4: Create GitHub Environments (Optional but Recommended)

GitHub environments provide an extra layer of protection:

1. Go to https://github.com/ACE-IoT-Solutions/ace-skyspark-lib/settings/environments
2. Create two environments:
   - **pypi**
     - Add protection rule: Required reviewers (optional)
     - Add deployment branch rule: `main` only
   - **testpypi**
     - No special protection needed

## Publishing a New Release

### Method 1: GitHub Release (Recommended)

1. **Update version in `pyproject.toml`:**
   ```toml
   version = "0.1.7"
   ```

2. **Update `CHANGELOG.md`** with release notes

3. **Commit and push:**
   ```bash
   git add pyproject.toml CHANGELOG.md
   git commit -m "Release v0.1.7"
   git push origin main
   ```

4. **Create GitHub Release:**
   - Go to https://github.com/ACE-IoT-Solutions/ace-skyspark-lib/releases/new
   - Click "Choose a tag"
   - Type `v0.1.7` and click "Create new tag: v0.1.7 on publish"
   - Release title: `v0.1.7`
   - Description: Copy relevant section from CHANGELOG.md
   - Click "Publish release"

5. **Watch the workflow:**
   - Go to https://github.com/ACE-IoT-Solutions/ace-skyspark-lib/actions
   - The "Publish to PyPI" workflow will run automatically
   - It will test, build, and publish to PyPI

6. **Verify publication:**
   - Check https://pypi.org/project/ace-skyspark-lib/
   - Test installation: `pip install ace-skyspark-lib`

### Method 2: Tag Push (TestPyPI Only)

For testing releases:

```bash
git tag v0.1.7-test
git push origin v0.1.7-test
```

This publishes to TestPyPI only, good for testing before the real release.

### Method 3: Manual Workflow Dispatch

For manual publishing:

1. Go to https://github.com/ACE-IoT-Solutions/ace-skyspark-lib/actions/workflows/publish.yml
2. Click "Run workflow"
3. Choose branch: `main`
4. Choose target: `testpypi` or `pypi`
5. Click "Run workflow"

## Workflow Details

### Jobs

1. **test** - Runs tests and linting on Python 3.11, 3.12, 3.13
2. **build** - Builds wheel and source distribution
3. **publish-to-testpypi** - Publishes to TestPyPI (for tags or manual dispatch)
4. **publish-to-pypi** - Publishes to PyPI (for releases or manual dispatch)

### Workflow Files

- `.github/workflows/publish.yml` - Publishing workflow
- `.github/workflows/ci.yml` - Continuous integration (runs on PRs and pushes)

## Troubleshooting

### "Trusted publisher configuration not found"

This means you haven't set up trusted publishing on PyPI yet. Follow Step 2 above.

### "Environment protection rules not satisfied"

If you set up required reviewers in GitHub environments, you need to approve the deployment:
1. Go to the workflow run
2. Click "Review deployments"
3. Select the environment and approve

### "Version already exists"

PyPI doesn't allow re-uploading the same version. You must:
1. Increment version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create a new release

### Tests failing

The workflow will not publish if tests fail. Fix the tests and push again.

## Security Benefits of Trusted Publishing

✅ **No API tokens to manage** - No secrets to store or rotate
✅ **Short-lived credentials** - OIDC tokens expire after use
✅ **Scoped to specific workflow** - Only this workflow can publish
✅ **Auditable** - All publishes are logged in GitHub Actions
✅ **Revocable** - Disable publishing by removing the PyPI configuration

## Local Publishing (Not Recommended)

If you need to publish locally (not recommended for production):

```bash
# Set up API token in ~/.pypirc or environment
export UV_PUBLISH_TOKEN="pypi-AgEIcHlwaS5vcmcC..."

# Build and publish
uv build
uv publish
```

## Support

- PyPI Trusted Publishing Docs: https://docs.pypi.org/trusted-publishers/
- GitHub Actions Docs: https://docs.github.com/en/actions
- Issues: https://github.com/ACE-IoT-Solutions/ace-skyspark-lib/issues
