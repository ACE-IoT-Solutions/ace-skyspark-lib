# Publishing to PyPI

This guide explains how to publish `ace-skyspark-lib` to PyPI.

## 🚀 Recommended: Automated Publishing with GitHub Actions

**This is the preferred method!** The project uses GitHub Actions with PyPI Trusted Publishing for secure, automated releases.

See **[.github/PYPI_SETUP.md](.github/PYPI_SETUP.md)** for complete setup instructions.

**Quick Summary:**
1. Set up Trusted Publishing on PyPI (one-time)
2. Update version in `pyproject.toml` and `CHANGELOG.md`
3. Create a GitHub Release with tag `v0.1.x`
4. GitHub Actions automatically tests, builds, and publishes to PyPI

---

## Manual Publishing (Alternative)

If you need to publish manually (not recommended for production), follow these instructions.

## Prerequisites

1. **PyPI Account**: Create an account at https://pypi.org/account/register/
2. **PyPI API Token**: Generate an API token at https://pypi.org/manage/account/token/
   - Scope: "Entire account" (for first-time publishing) or "Project: ace-skyspark-lib"
   - Save the token securely - you'll only see it once

## One-Time Setup

### Configure API Token

Create or update `~/.pypirc`:

```ini
[pypi]
username = __token__
password = pypi-AgEIcHlwaS5vcmcC...  # Your API token here
```

Set proper permissions:
```bash
chmod 600 ~/.pypirc
```

Alternatively, use environment variable:
```bash
export UV_PUBLISH_TOKEN="pypi-AgEIcHlwaS5vcmcC..."
```

## Publishing Process

### 1. Verify Package Version

Check that version is updated in `pyproject.toml`:
```toml
version = "0.1.6"  # Current version
```

### 2. Update CHANGELOG.md

Ensure all changes for this version are documented.

### 3. Run Tests

```bash
uv run pytest tests/ --ignore=tests/test_aiohttp_direct.py --ignore=tests/test_with_requests.py
```

### 4. Build Package

```bash
uv build
```

This creates:
- `dist/ace_skyspark_lib-X.Y.Z-py3-none-any.whl`
- `dist/ace_skyspark_lib-X.Y.Z.tar.gz`

### 5. Check Package Metadata

```bash
# Inspect built package
tar -tzf dist/ace_skyspark_lib-0.1.6.tar.gz | head -20

# Validate package
uv run twine check dist/ace_skyspark_lib-0.1.6*
```

### 6. Test on TestPyPI (Optional but Recommended)

First publish to TestPyPI to verify everything works:

```bash
# Upload to TestPyPI
uv publish --publish-url https://test.pypi.org/legacy/

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ ace-skyspark-lib
```

### 7. Publish to PyPI

```bash
uv publish
```

Or with explicit token:
```bash
uv publish --token $UV_PUBLISH_TOKEN
```

### 8. Verify Publication

Visit: https://pypi.org/project/ace-skyspark-lib/

Test installation:
```bash
pip install ace-skyspark-lib
```

### 9. Create Git Tag

```bash
git tag -a v0.1.6 -m "Release v0.1.6"
git push origin v0.1.6
```

### 10. Create GitHub Release

Go to: https://github.com/ACE-IoT-Solutions/ace-skyspark-lib/releases/new
- Tag: v0.1.6
- Title: v0.1.6
- Description: Copy from CHANGELOG.md

## Troubleshooting

### Authentication Errors

If you get authentication errors:
```bash
# Check ~/.pypirc permissions
ls -la ~/.pypirc

# Should show: -rw------- (600)
chmod 600 ~/.pypirc
```

### Version Already Exists

PyPI doesn't allow re-uploading the same version. You must:
1. Increment version in `pyproject.toml`
2. Update CHANGELOG.md
3. Rebuild: `uv build`
4. Publish again: `uv publish`

### Missing Metadata

If build fails, check:
- README.md exists and is valid Markdown
- LICENSE file exists
- All required fields in pyproject.toml are filled

## Package Metadata Checklist

✅ Version number updated
✅ CHANGELOG.md updated
✅ Tests passing
✅ README.md complete
✅ LICENSE file present
✅ Project URLs configured
✅ Python version compatibility specified
✅ Dependencies listed correctly
✅ Classifiers appropriate

## Security Notes

- **Never commit API tokens** to version control
- Store tokens in `~/.pypirc` with 600 permissions
- Use project-scoped tokens when possible
- Rotate tokens periodically
- Use 2FA on your PyPI account

## Support

- PyPI Documentation: https://packaging.python.org/
- uv Publishing Guide: https://docs.astral.sh/uv/guides/publish/
- PyPI Help: https://pypi.org/help/
