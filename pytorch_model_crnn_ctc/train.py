import argparse
import os
import torch
import cv2 as cv
import numpy as np
import torch.nn.functional as F
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import StepLR
from torch.utils.data import DataLoader
from torch.utils.data import Dataset
# import torchvision.models as models

PICS_PATH = "/home/yxy/project/car_plate/data/train"

CHARS = {"京": 0, "沪": 1, "津": 2, "渝": 3, "冀": 4, "晋": 5, "蒙": 6, "辽": 7, "吉": 8, "黑": 9, "苏": 10,
         "浙": 11, "皖": 12, "闽": 13, "赣": 14, "鲁": 15, "豫": 16, "鄂": 17, "湘": 18, "粤": 19, "桂": 20,
         "琼": 21, "川": 22, "贵": 23, "云": 24, "藏": 25, "陕": 26, "甘": 27, "青": 28, "宁": 29, "新": 30,
         "0": 31, "1": 32, "2": 33, "3": 34, "4": 35, "5": 36, "6": 37, "7": 38, "8": 39, "9": 40, "A": 41,
         "B": 42, "C": 43, "D": 44, "E": 45, "F": 46, "G": 47, "H": 48, "J": 49, "K": 50, "L": 51, "M": 52,
         "N": 53, "P": 54, "Q": 55, "R": 56, "S": 57, "T": 58, "U": 59, "V": 60, "W": 61, "X": 62, "Y": 63,
         "Z": 64, "-": 65}

CHARS_LIST = ["京", "沪", "津", "渝", "冀", "晋", "蒙", "辽", "吉", "黑",
         "苏", "浙", "皖", "闽", "赣", "鲁", "豫", "鄂", "湘", "粤",
          "桂", "琼", "川", "贵", "云", "藏", "陕", "甘", "青", "宁", "新",
          "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B",
          "C", "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P",
          "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "-"]

def parseOutput(indexs):
    label = ""
    for i in range(indexs.shape[0]):
        latter = CHARS_LIST[indexs[i]]
        #if latter != "-":
        label += latter
    return label

class CarPlateLoader(Dataset):
    def __init__(self, pics):
        self.pics = pics

    def __len__(self):
        return len(self.pics)

    def __getitem__(self, item):
        img = cv.imread(PICS_PATH + "/" + self.pics[item])
        # img = cv.resize(img, (160, 32))
        r, g, b = cv.split(img)
        numpy_array = np.array([r, g, b])
        label = self.pics[item][0:7]

        img_tensor = torch.from_numpy(numpy_array)
        img_tensor = img_tensor.float()
        img_tensor /= 256

        label_tensor = torch.zeros(7, dtype=torch.int)
        for i in range(7):
            label_tensor[i] = int(CHARS[label[i]])
        return {"img": img_tensor, "label": label_tensor}

class FeatureMap(torch.nn.Module):
    def __init__(self, batch):
        super(FeatureMap, self).__init__()
        self.batch = batch

    def forward(self, x):
        # 分块
        x = torch.split(x, 2, dim=3)
        tl = []
        for i in range(len(x)):
            tmp = x[i].reshape(self.batch, 32 * 8 * 2)
            tl.append(tmp)
        out = torch.stack(tl, dim=1)
        return out

class VGG16(nn.Module):
    def __init__(self):
        super(VGG16, self).__init__()
        
        # 3 * 224 * 224
        self.conv1_1 = nn.Conv2d(3, 64, 3) # 64 * 222 * 222
        self.conv1_2 = nn.Conv2d(64, 64, 3, padding=(1, 1)) # 64 * 222* 222
        self.maxpool1 = nn.MaxPool2d((2, 2), padding=(1, 1)) # pooling 64 * 112 * 112
        
        self.conv2_1 = nn.Conv2d(64, 128, 3) # 128 * 110 * 110
        self.conv2_2 = nn.Conv2d(128, 128, 3, padding=(1, 1)) # 128 * 110 * 110
        self.maxpool2 = nn.MaxPool2d((2, 2), padding=(1, 1)) # pooling 128 * 56 * 56
        
        self.conv3_1 = nn.Conv2d(128, 256, 3) # 256 * 54 * 54
        self.conv3_2 = nn.Conv2d(256, 256, 3, padding=(1, 1)) # 256 * 54 * 54
        self.conv3_3 = nn.Conv2d(256, 256, 3, padding=(1, 1)) # 256 * 54 * 54
        self.maxpool3 = nn.MaxPool2d((2, 2), padding=(1, 1)) # pooling 256 * 28 * 28
        
        self.conv4_1 = nn.Conv2d(256, 512, 3) # 512 * 26 * 26
        self.conv4_2 = nn.Conv2d(512, 512, 3, padding=(1, 1)) # 512 * 26 * 26
        self.conv4_3 = nn.Conv2d(512, 512, 3, padding=(1, 1)) # 512 * 26 * 26
        self.maxpool4 = nn.MaxPool2d((2, 2), padding=(1, 1)) # pooling 512 * 14 * 14
        
        self.conv5_1 = nn.Conv2d(512, 512, 3) # 512 * 12 * 12
        self.conv5_2 = nn.Conv2d(512, 512, 3, padding=(1, 1)) # 512 * 12 * 12
        self.conv5_3 = nn.Conv2d(512, 512, 3, padding=(1, 1)) # 512 * 12 * 12
        self.maxpool5 = nn.MaxPool2d((3, 3), padding=(1, 1)) # pooling 512 * 7 * 7
        
        # view
        
        # self.fc1 = nn.Linear(512 * 7 * 7, 4096)
        # self.fc2 = nn.Linear(4096, 4096)
        # self.fc3 = nn.Linear(4096, 1000)
        # softmax 1 * 1 * 1000
        
    def forward(self, x):
        
        # x.size(0)即为batch_size
        in_size = x.size(0)
        
        out = self.conv1_1(x) # 222
        out = F.relu(out)
        out = self.conv1_2(out) # 222
        out = F.relu(out)
        out = self.maxpool1(out) # 112
        
        out = self.conv2_1(out) # 110
        out = F.relu(out)
        out = self.conv2_2(out) # 110
        out = F.relu(out)
        out = self.maxpool2(out) # 56
        
        out = self.conv3_1(out) # 54
        out = F.relu(out)
        out = self.conv3_2(out) # 54
        out = F.relu(out)
        out = self.conv3_3(out) # 54
        out = F.relu(out)
        out = self.maxpool3(out) # 28
        
        out = self.conv4_1(out) # 26
        out = F.relu(out)
        out = self.conv4_2(out) # 26
        out = F.relu(out)
        out = self.conv4_3(out) # 26
        out = F.relu(out)
        out = self.maxpool4(out) # 14
        
        out = self.conv5_1(out) # 12
        out = F.relu(out)
        out = self.conv5_2(out) # 12
        out = F.relu(out)
        out = self.conv5_3(out) # 12
        out = F.relu(out)
        out = self.maxpool5(out) # 7
        
        # 展平
        # out = out.view(in_size, -1)
        
        # out = self.fc1(out)
        # out = F.relu(out)
        # out = self.fc2(out)
        # out = F.relu(out)
        # out = self.fc3(out)
        
        # out = F.log_softmax(out, dim=1)

        return out

class Net(torch.nn.Module):
    def __init__(self, batch, device, num_layers):
        super(Net, self).__init__()
        self.batch = batch
        self.device = device
        # self.conv1 = nn.Conv2d(3, 32, 3, padding=1)
        # self.conv2 = nn.Conv2d(32, 64, 3, padding=1)
        # self.conv3 = nn.Conv2d(64, 64, 3, padding=1)
        # self.conv4 = nn.Conv2d(64, 32, 3, padding=1)
        self.vgg16 = VGG16()
         # an affine operation: y = Wx + b
        self.num_layers = num_layers
        # self.gru1 = nn.GRU(32*16, 128, num_layers=self.num_layers, bidirectional=True, dropout=0.3)
        self.lstm = nn.LSTM(32*16, 128, num_layers=self.num_layers, bidirectional=True, dropout=0.3)

        # self.fm = FeatureMap(self.batch)
        self.fc = nn.Linear(256, 66)
        #2*10  4*20 8*40 16*80 32*160

    def forward(self, x):
        # x = F.leaky_relu(self.conv1(x))
        # x = F.leaky_relu(self.conv2(x))
        # x = F.max_pool2d(x, (2, 2))
        # x = F.leaky_relu(self.conv3(x))
        # x = F.leaky_relu(self.conv4(x))
        # x = F.max_pool2d(x, (2, 2))
        x = self.vgg16(x)
        b, c, h, w = x.size()
        assert h == 1
        # x = self.fm(x)
        x = x.squeeze(2)
        # 维度转换
        x = x.permute(2, 0, 1)
        # x, h = self.gru1(x)
        x, h = self.lstm(x)
        x = self.fc(x)
        x = F.log_softmax(x, dim=2)
        return x


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--epoes', type=int, default=30, help='train epoes')
    parser.add_argument('--lr', type=float, default=0.0001, help='train epoes')
    parser.add_argument('--batch', type=int, default=10, help='batch size')
    return parser.parse_args()


def main(args):
    pics = os.listdir(PICS_PATH)
    data_set = CarPlateLoader(pics)
    data_loader = DataLoader(data_set, batch_size=args.batch, shuffle=True, num_workers=8)

    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    model = Net(args.batch, device, 2).to(device)
    # if os.path.exists("car_plate.pt"):
    #     model.load_state_dict(torch.load("car_plate.pt"))
    optimizer = optim.Adam(model.parameters(), lr=args.lr)
    scheduler = StepLR(optimizer, step_size=10, gamma=0.9)
    for i in range(args.epoes):
        model.train()
        for i_batch, sample_batched in enumerate(data_loader):
            optimizer.zero_grad()
            img_tensor = sample_batched["img"].to(device)
            label_tensor = sample_batched["label"].to(device)
            if label_tensor.shape[0] != args.batch:
                continue
            output = model(img_tensor)
            inputs_size = torch.zeros(label_tensor.shape[0], dtype=torch.int)
            for ii in range(inputs_size.shape[0]):
                inputs_size[ii] = output.shape[0]
            targets_size = torch.zeros(label_tensor.shape[0], dtype=torch.int)
            for iii in range(targets_size.shape[0]):
                targets_size[iii] = label_tensor[iii].shape[0]
            loss = F.ctc_loss(output, label_tensor, inputs_size, targets_size, blank=65)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 400)
            optimizer.step()
            if i_batch % 100 == 0:
                tmp = torch.squeeze(output.cpu()[:, 0, :])
                values, indexs = tmp.max(1)
                print(i, i_batch, "loss=" + str(loss.cpu().item()), "lr=" + str(scheduler.get_lr()),
                      ",random check: label is " + parseOutput(label_tensor[0]) + " ,network predict is " + parseOutput(indexs))
        scheduler.step()

    torch.save(model.state_dict(), "car_plate_vgg16.pt")


if __name__ == '__main__':
    main(parse_args())
