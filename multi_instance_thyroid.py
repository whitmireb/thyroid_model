# -*- coding: utf-8 -*-
"""Multi_Labeled_Thyroid_Detection_Model_Revised.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1DDvH0GZv4cIUl6DmZ-0Z1eSRkHb8itUv

# Import from google drive to get the data
"""


"""# Import main packages and modules"""

# Here we are importing our basic modules
import os
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
# import seaborn as sns
import torch
import shutil
# import helpers

"""Add the below path to system path so that python files stored in the path can be imported"""

# import sys
# sys.path.append('/content/drive/MyDrive/Thyroid_Data/NOH_Runs')

from sklearn import model_selection, metrics

import torch
import torchvision
from torchvision.transforms import v2
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import ReduceLROnPlateau
from efficientnet_pytorch import EfficientNet
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from torch.utils.data import DataLoader
from tqdm.auto import tqdm
from sklearn.cluster import KMeans
import pdb

from PIL import Image
import re
from PIL import ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Import utility functions
# from cjm_pandas_utils.core import markdown_to_pandas
# from cjm_pil_utils.core import resize_img
# from cjm_pytorch_utils.core import set_seed, pil_to_tensor, tensor_to_pil, get_torch_device, denorm_img_tensor 
from torchvision.transforms import v2
from torchvision.io import read_image
torch.manual_seed(62)
np.random.seed(62) #60

"""# Load data"""

# Load the data from my google drive
noh_fp = 'NOH'

"""# Gather data from csv file"""

noh_data = pd.read_csv('data_NOH.csv')

# This just strips the data to ensure there is no repeats and showcases a break down of value counts
noh_data[['Patient #', 'Surgery diagnosis in number']].drop_duplicates()['Surgery diagnosis in number'].value_counts().sort_index()

"""# Plotting a graph of number of patients
Break down of cancer and non-cancer
"""

foldk = 'fold_3'

# Connect each image link to a test and train split
noh_data['image_path'] = noh_data.apply(lambda row: row.image_path.replace('../data','/content/drive/MyDrive/Thyroid_Data/Runs'), axis = 1)

# Show the plot of the image address, the label of the image, and if it is testing or training data
img_ds = noh_data[['image_path', 'Surgery diagnosis in number', foldk, 'Patient #']]
img_ds


"""# Define testing and training transformers"""

# Create transforms for train and test data
train_transform = v2.Compose([
    v2.ToImage(),
    v2.ToDtype(torch.float32, scale=True),
    v2.Resize(224, antialias=True),
    v2.RandomCrop(224),
    v2.RandomVerticalFlip(p=0.5),
    v2.RandomHorizontalFlip(p=0.5),
    v2.RandomRotation(degrees=30),
    v2.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

test_transform = v2.Compose([
    v2.ToImage(),
    v2.ToDtype(torch.float32, scale=True),
    v2.Resize(224, antialias=True), #224
    v2.CenterCrop(size=224),
    v2.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

"""## Batch size"""

# Define a batch size for the AI model
'''Could attempt increasing batch size on my PC'''
batch_size=16

"""# Dataset and dataloader"""

import torch
from PIL import Image
import os

class NOHThyroidDataset(torch.utils.data.Dataset):
    def __init__(self, dataframe, base_path, transform=None):
        self.dataframe = dataframe
        self.base_path = base_path  # Define the base path in the constructor
        self.transform = transform

    def __len__(self):
        return len(self.dataframe)

    def __getitem__(self, idx):
        # Get the relative image path from the dataframe and append it to the base path
        image_path = os.path.join(self.base_path, self.dataframe['image_path'][idx].replace("\\", "/"))
        label = self.dataframe['Surgery diagnosis in number'][idx]

        # Open the image
        image = Image.open(image_path)

        # Apply any transformation (if available)
        if self.transform:
            image = self.transform(image)

        return image, label

class BaggedDataset(torch.utils.data.Dataset):
    def __init__(self, dataframe, base_path, transform=None):
        self.dataframe = dataframe
        self.base_path = base_path  # Define the base path in the constructor
        self.transform = transform

    def __len__(self):
        return len(self.dataframe['Patient #'].unique())

    def __getitem__(self, idx):
        # Get the relative image path from the dataframe and append it to the base path
        # 130, 33, 42, 47, 49, 51, 55, 58, 59, 60, 62, 64, 76, 80, 85, 89, 91, 92, 98, 105, 110, 111, 113, 114, 116, 126
        # all_patient_numbers = set(range(1, 133))  # Adjust range if needed
        existing_patient_numbers = self.dataframe['Patient #'].unique()
        # missing_patient_numbers = all_patient_numbers - existing_patient_numbers

        # if missing_patient_numbers:
        #     print(f"Missing patient numbers: {missing_patient_numbers}")

        image_paths = [os.path.join(self.base_path, image_path.replace("\\", "/")) for image_path in self.dataframe[self.dataframe['Patient #'] == existing_patient_numbers[idx]]['image_path']]
        label = self.dataframe[self.dataframe['Patient #'] == existing_patient_numbers[idx]]['Surgery diagnosis in number'].iloc[0]
        # Open the image
        images = [Image.open(image_path) for image_path in image_paths]

        # Apply any transformation (if available)
        if self.transform:
            images = [self.transform(image) for image in images]

        return images, label

# This is used for data spliting
train_df = img_ds[img_ds[foldk]=='train'].reset_index(drop=True)
test_df = img_ds[img_ds[foldk]=='test'].reset_index(drop=True)

"""# Define test and train loaders"""

# Define the base path to the folder containing the images on Google Drive
base_path = ""

# Create the dataset, passing the base path to it
train_dataset = BaggedDataset(dataframe=train_df, base_path=base_path, transform=train_transform)

# Create the DataLoader
trainloader = torch.utils.data.DataLoader(train_dataset, batch_size=1, shuffle=True)

# Define the base path to the folder containing the images on Google Drive
base_path = ""

# Create the dataset, passing the base path to it
test_dataset = NOHThyroidDataset(dataframe=test_df, base_path=base_path, transform=test_transform)

# Create the DataLoader
testloader = torch.utils.data.DataLoader(test_dataset, batch_size=32, shuffle=True)

# Set the standard stats
norm_stats = ((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))

# If there is a device, take the first else use the CPU
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

class Classifier(nn.Module):
    def __init__(self, in_features):
        super(Classifier, self).__init__()
        self.fc = nn.Linear(in_features, 1)
    
    def forward(self, x):
        x = torch.flatten(x, 1)
        return self.fc(x)

class AttentionPooling(nn.Module):
    def __init__(self, feature_dim, hidden_dim=128):
        super(AttentionPooling, self).__init__()
        # Attention network: Two-layer MLP to compute attention scores
        self.attention_fc = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim),  # First layer
            nn.Tanh(),  # Non-linearity
            nn.Linear(hidden_dim, 1)  # Single attention score per instance
        )

    def forward(self, features):
        """
        :param features: Tensor of shape (num_instances, feature_dim)
        :return: Pooled feature representation of the bag (weighted sum)
        """
        # Step 1: Compute attention scores (un-normalized) for each instance
        attention_scores = self.attention_fc(features)  # Shape: (num_instances, 1)

        # Step 2: Normalize the attention scores using softmax so they sum to 1
        attention_weights = torch.softmax(attention_scores, dim=0)  # Shape: (num_instances, 1)

        # Step 3: Weighted sum of the instance features using the attention weights
        pooled_features = torch.sum(attention_weights * features, dim=0)  # Shape: (feature_dim,)

        return pooled_features  # Return the pooled bag-level feature representation

# Load the pretrained weights onto the model
# feature_extractor = FeatureExtractor()

# ----------------------------------------------
from torchvision import models
efficientnet = models.efficientnet_b0(weights='IMAGENET1K_V1')

# Remove the final classification layer
feature_extractor = nn.Sequential(
    *list(efficientnet.children())[:-1]  # Exclude the final classification layer
)
feature_extractor.conv1x1 = nn.Conv2d(1280, 128, kernel_size=1)
# ----------------------------------------------

dummy_input = torch.randn(1, 3, 224, 224)  # Adjust the dimensions if necessary
output = feature_extractor(dummy_input)
num_features = output.shape[1]

classifier = Classifier(in_features=num_features) # num_classes= train_df['Surgery diagnosis in number'].nunique()
feature_extractor = feature_extractor.to(device)
classifier = classifier.to(device)
feature_extractor.eval()
attention_pooling = AttentionPooling(feature_dim=128)

# Set the number of epochs and the best accuracy
num_epochs = 25
best_val_acc = 0.0
all_accs = []

'''This is where we can make alot of changes to test and see what works better'''
# This is to define our standard loss function
criterion = nn.BCELoss()
# Set up our learning rate with Adam
optimizer = optim.Adam(classifier.parameters(), lr=1e-4, weight_decay=1e-4) #weight_decay=1e-4
# Define some of our other factors, such as stoppage, patience, and verbose for the model
scheduler = ReduceLROnPlateau(optimizer, 'min', factor=0.3, patience=3)

# This functions is used to evaluate and display the proformance of our classification model
def report_clf(preds_ts, outs_ts):
    np_preds = [i.numpy() for i in preds_ts]
    np_outs = [i.numpy() for i in outs_ts]

    np_preds = np.array([i for s in np_preds for i in s])
    np_outs = np.array([i for s in np_outs for i in s])
    assert np_preds.shape == np_outs.shape

    print(metrics.classification_report(np_outs, np_preds))

    cm = metrics.confusion_matrix(np_outs, np_preds)
    d = metrics.ConfusionMatrixDisplay(cm)
    d.plot()
    plt.show()

# This is used to evaluate the model when ran on a dataset
def evaluate_dataset(model, ds_loader):
    model.eval()
    loss = 0.0
    acc = 0.0
    preds = []
    outs = []
    for _, (data, target) in enumerate(tqdm(ds_loader)):
        data, target = data.to(device), target.to(device)
        output = model(data)
        loss = criterion(output, target)
        loss += loss.item()
        acc += accuracy_score(output.cpu().argmax(dim=1), target.cpu())
        preds.append(output.cpu().argmax(dim=1))
        outs.append(target.cpu())

    loss /= len(testloader)
    acc /= len(testloader)
    print('Test Loss: {:.4f} \tTest Acc: {:.4f}'.format(loss, acc))
    report_clf(preds, outs)
    return acc,preds, outs

# Adjust bag features using the confounders
def apply_backdoor_adjustment(bag_features, confounder_centroids, alpha=0.1):
    adjusted_bag_features = bag_features.clone()
    
    for confounder in confounder_centroids:
        confounder = torch.tensor(confounder).to(bag_features.device)  # Convert confounder to a tensor
        confounder = confounder.detach()  # Detach to avoid gradients
        
        # Compute the distance between the bag features and the confounder
        distance = torch.norm(bag_features - confounder, dim=-1)
        
        # Adjust the bag features with the confounder
        adjusted_bag_features += alpha * confounder / (distance + 1e-5)
    
    return adjusted_bag_features


# Run a new model to see how well it does
# for epoch in range(num_epochs):
#     classifier.train()
#     train_loss = 0.0
#     train_acc = 0.0
#     for batch_idx, (data, target) in enumerate(tqdm(trainloader)):
#         data = torch.stack([image for image in data])
#         data = data.squeeze(1)
#         target = target.to(device)
#         optimizer.zero_grad()
#         features = feature_extractor(data)
#         features = features.mean(dim=0).squeeze(1).T
#         output = classifier(features) #The classifier will give the real output
#         loss = criterion(output, target)
#         loss.backward()
#         optimizer.step()
#         train_loss += loss.item()
#         train_acc += accuracy_score(output.cpu().argmax(dim=1), target.cpu())
#     train_loss /= len(trainloader)
#     train_acc /= len(trainloader)

#     classifier.eval()
#     val_loss = 0.0
#     val_acc = 0.0
#     for batch_idx, (data, target) in enumerate(tqdm(testloader)):
#         data, target = data.to(device), target.to(device)
#         features = feature_extractor(data)
#         output = classifier(features)
#         loss = criterion(output, target)
#         val_loss += loss.item()
#         val_acc += accuracy_score(output.cpu().argmax(dim=1), target.cpu())
#     val_loss /= len(testloader)
#     val_acc /= len(testloader)
#     all_accs.append(val_acc)

#     scheduler.step(val_loss)

#     print('Epoch: {} \tTrain Loss: {:.4f} \tTrain Acc: {:.4f} \tVal Loss: {:.4f} \tVal Acc: {:.4f}'.format(
#         epoch, train_loss, train_acc, val_loss, val_acc))

"""Grab the confounders for data alteration"""
# The number of confounders
num_clusters = 8

all_bag_features = []
print('Loading the confounders...')
with torch.no_grad():
    for batch_idx, (data, target) in enumerate(tqdm(trainloader)):
        data = torch.stack([image for image in data]).squeeze(1)
        data = data.to(device)

        # Feature extraction for instances in the bag
        instance_features = feature_extractor(data)
  
        # Aggregate instance features (mean-pooling or max-pooling)
        bag_features = instance_features.mean(dim=0)

        # Store the bag-level feature representation
        all_bag_features.append(bag_features.cpu().numpy())

all_bag_features = np.array(all_bag_features)
all_bag_features = all_bag_features.squeeze(2).squeeze(2)
kmeans = KMeans(n_clusters=num_clusters, random_state=0).fit(all_bag_features)
confounder_centroids = kmeans.cluster_centers_ 

for epoch in range(num_epochs):
    classifier.train()  # Set model to training mode
    train_loss = 0.0
    train_acc = 0.0
    
    # Training loop
    print(f"Training for epoch {epoch}...")
    for batch_idx, (data, target) in enumerate(tqdm(trainloader)):
        data = torch.stack([image for image in data]).squeeze(1)  # Prepare input
        data, target = data.to(device), target.to(device)
        
        optimizer.zero_grad()
        
        # Feature extraction and classification
        instance_features = feature_extractor(data)
        # bag_features = instance_features.mean(dim=0).squeeze(1).T  # mean pooling
        bag_features = attention_pooling(instance_features)
        adjusted_features = apply_backdoor_adjustment(bag_features, confounder_centroids, 0.001)
        output = classifier(adjusted_features)
        
        # Calculate loss and backpropagate
        loss = criterion(output, target)
        loss.backward()
        optimizer.step()
        
        # Track training loss and accuracy
        train_loss += loss.item()
        train_acc += accuracy_score(output.cpu().argmax(dim=1), target.cpu())
    
    # Calculate average training loss and accuracy
    train_loss /= len(trainloader)
    train_acc /= len(trainloader)
    
    # Validation loop
    classifier.eval()  # Set model to evaluation mode
    val_loss = 0.0
    val_acc = 0.0
    
    print(f"Testing for epoch {epoch}...")
    with torch.no_grad():  # Disable gradient computation for validation
        for batch_idx, (data, target) in enumerate(tqdm(testloader)):
            data = torch.stack([image for image in data]).squeeze(1)  # Prepare input
            data, target = data.to(device), target.to(device)
            
            # Feature extraction and classification
            features = feature_extractor(data)
            output = classifier(features)
            
            # Calculate validation loss
            loss = criterion(output, target)
            val_loss += loss.item()
            
            # Track validation accuracy
            val_acc += accuracy_score(output.cpu().argmax(dim=1), target.cpu())
    
    # Calculate average validation loss and accuracy
    val_loss /= len(testloader)
    val_acc /= len(testloader)
    
    all_accs.append(val_acc)

    # Learning rate scheduler step based on validation loss
    scheduler.step(val_loss)
    
    # Print epoch summary
    print(f'Epoch: {epoch} \tTrain Loss: {train_loss:.4f} \tTrain Acc: {train_acc:.4f} \tVal Loss: {val_loss:.4f} \tVal Acc: {val_acc:.4f}')

print(all_accs)