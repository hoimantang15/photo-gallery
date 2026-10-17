# 1. Initialize git in your folder (if not already done) 
git init  

# 2. Add your files and commit them 
git add main.py requirements.txt 
git commit -m "Initial commit with main.py and requirements.txt"  

# 3. Rename branch to main 
git branch -M main  

# 4. Link to your GitHub repository 
git remote add origin https://github.com/hoimantang15/photo-gallery.git

# 5. Push your code 
git push -u origin main 