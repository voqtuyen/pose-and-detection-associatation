## Installation
```python3
git clone https://github.com/voqtuyen/pose-and-detection-associatation.git
```

## Directory structure
```bash
.
├── annotations
├── images
├── keypoints
├── pose_association.py
└── README.md
```
- Put all annotations files in Pascal VOC in annotations directory
- Put all keypoints files generated by Pose-based annotation tool
## Run
```python3
python3 pose_association.py --anno_dir annotations --keypoint_dir keypoints
```
## Future feature
- Handle cases where number of bboxes generated by pose-based annotation tool and bboxes generated by SSD/Yolo detector

## Release history
- 0.1 Initial version (Sep 13, 2018)
- 0.5 Add keypoints association and handle different lengths of det and kpts( Sep 17, 2018)
