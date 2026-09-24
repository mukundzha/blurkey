# blurkey demo: one command. Fakes only (AWS-documented example key).
Output "demo/demo.gif"
Set Shell "bash"
Set FontFamily "JetBrains Mono"
Set FontSize 20
Set Width 1080
Set Height 360
Set Theme "Catppuccin Mocha"
Set Padding 24
Set BorderRadius 12
Set WindowBarSize 30
Set TypingSpeed 0.07

Hide
Type `cd demo && rm -f app.redacted*.png && clear` Enter
Sleep 1s
Show

Type `blurkey app.png` Enter
Sleep 12s
