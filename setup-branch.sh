#!/bin/bash
# MCN Branch Setup Script

CURRENT_BRANCH=$(git branch --show-current)

if [ "$CURRENT_BRANCH" = "main" ]; then
    echo "Main branch - Production ready"
    # Ensure develop-docs is ignored
    if [ -d "develop-docs" ]; then
        echo "develop-docs found in main branch - removing"
        rm -rf develop-docs
    fi
    
elif [ "$CURRENT_BRANCH" = "develop" ]; then
    echo "Develop branch - Development mode"
    # Create develop-docs if it doesn't exist
    if [ ! -d "develop-docs" ]; then
        echo "Creating develop-docs folder"
        mkdir -p develop-docs
        
        # Create development files
        cat > develop-docs/README.md << 'EOF'
# MCN Development Documentation

This folder contains development-specific documentation that is only available in the develop branch.

## Contents
- Language specifications
- Governance documents  
- Industry adoption strategies
- Development roadmaps
- Internal documentation

## Branch Policy
This folder is excluded from the main branch to keep production clean and focused.
EOF
    fi
    
    # Remove develop-docs from .gitignore in develop branch
    if [ -f ".gitignore" ]; then
        sed -i.bak '/develop-docs\//d' .gitignore
        rm -f .gitignore.bak
    fi
    
else
    echo "Branch: $CURRENT_BRANCH"
fi