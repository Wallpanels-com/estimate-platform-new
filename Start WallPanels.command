#!/bin/zsh
cd -- "${0:A:h}"
npm run dev && open -a 'Google Chrome' 'http://localhost:5190'
