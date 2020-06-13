Usage:

```
./run.sh
```

Three windows will open and opencv will start running motion detection. 

When any contours are detected (movement of detected object), opencv will
shutdown and handover recording to ffmpeg, which will start capturing at
4k30fps for 10 minutes.

After ffmpeg terminates, the script will shutdown.

Output:

```
<timestamp>.mkv
```
