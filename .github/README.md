# GitHub Actions Workflows

This directory contains automated workflows for CI/CD.

## Workflows

### [`ci.yml`](workflows/ci.yml)
**Continuous Integration**

Runs on every push to `main` and on all pull requests.

- Tests on Python 3.11, 3.12, 3.13
- Runs linting (ruff)
- Runs unit tests

### [`publish.yml`](workflows/publish.yml)
**PyPI Publishing**

Automatically publishes to PyPI when you create a GitHub release.

**Triggers:**
- GitHub Release published → PyPI
- Tag push (`v*`) → TestPyPI
- Manual dispatch → Choose target

**Jobs:**
1. Run tests on all Python versions
2. Build wheel and source distribution
3. Publish to PyPI or TestPyPI

## Setup Instructions

See **[PYPI_SETUP.md](PYPI_SETUP.md)** for complete setup instructions for PyPI Trusted Publishing.

## Trusted Publishing (OIDC)

This project uses PyPI's Trusted Publishing feature which uses OpenID Connect (OIDC) for authentication. This means:

✅ No API tokens needed
✅ More secure than traditional token-based auth
✅ Automatic credential management
✅ Scoped to specific workflows only

## Quick Start for Publishing

1. **Update version and changelog:**
   ```bash
   # Edit pyproject.toml - bump version
   # Edit CHANGELOG.md - add release notes
   git add pyproject.toml CHANGELOG.md
   git commit -m "Release v0.1.7"
   git push origin main
   ```

2. **Create GitHub Release:**
   - Go to https://github.com/ACE-IoT-Solutions/ace-skyspark-lib/releases/new
   - Tag: `v0.1.7`
   - Title: `v0.1.7`
   - Description: Copy from CHANGELOG
   - Click "Publish release"

3. **Watch it publish:**
   - GitHub Actions will automatically run
   - Monitor at https://github.com/ACE-IoT-Solutions/ace-skyspark-lib/actions

4. **Verify:**
   - Check https://pypi.org/project/ace-skyspark-lib/
   - Test: `pip install ace-skyspark-lib`

## Support

- GitHub Actions Docs: https://docs.github.com/en/actions
- PyPI Trusted Publishing: https://docs.pypi.org/trusted-publishers/
- Issues: https://github.com/ACE-IoT-Solutions/ace-skyspark-lib/issues
