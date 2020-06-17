import torch
from torch import nn, optim
from torch.autograd import Variable
from backend.config import BACKEND
from backend.data.dataloader import DataLoader
from backend.loss.center_loss import CenterLoss
from backend.model import embed_fasttext
from backend.model.intent_bilstm import IntentBiLSTM
from backend.proc.gensim_processor import GensimProcessor
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


def visualize(feat, labels):
    pc_y = np.c_[feat, labels]
    df = pd.DataFrame(pc_y, columns=['PC1', 'PC2', 'diagnosis'])
    fig = plt.figure()
    ax = fig.add_subplot()
    ax.scatter(df['PC1'], df['PC2'], marker='o', c=df['diagnosis'])
    plt.savefig('image.png')


def test(test_data, model):
    correct, total = 0, 0
    test_data, test_label = test_data
    x = Variable(test_data).cuda()
    y = Variable(test_label).cuda()
    feature = model(x)

    retrieval = model.retrieval(feature)
    classification = model.classifier(retrieval)

    _, predicted = torch.max(classification.data, 1)
    total += y.size(0)
    correct += (predicted == y.data).sum()

    print("TEST ACC : {}".format((100 * correct / total)))


def train(train_data, model, criterion, opt, batch_size, loss_weight, label_dict):
    vis_loader, idx_loader = [], []
    losses, acccs = 0, 0
    for i, (x, y) in enumerate(train_data):
        x = Variable(x.cuda())
        y = Variable(y.cuda())
        model = model.cuda()
        feature = model(x)

        retrieval = model.retrieval(feature).cuda()
        classification = model.classifier(retrieval).cuda()
        _, predicted = torch.max(classification.data, 1)
        accuracy = (y.data == predicted).float().mean()

        loss = criterion[0](classification, y)
        loss += loss_weight * criterion[1](retrieval, y)

        opt[0].zero_grad()
        opt[1].zero_grad()

        loss.backward()

        opt[0].step()
        opt[1].step()

        vis_loader.append(retrieval)
        idx_loader.append(y)
        losses += loss
        acccs += accuracy

    print("loss : {0}, acc : {1}".format(losses / len(train_data), acccs / len(train_data)))
    feat = torch.cat(vis_loader, 0)
    labels = torch.cat(idx_loader, 0)
    visualize(feat.detach().cpu().numpy(), labels.detach().cpu().numpy(), label_dict, batch_size)


def main():
    data_loader = DataLoader()
    embed = GensimProcessor(embed_fasttext)
    # embed.train(data_loader.embed_dataset())
    embed.load_model()

    dataset = data_loader.intent_dataset(embed)
    train_data, test_data = dataset

    model = IntentBiLSTM(
        d_model=2,
        label_dict=data_loader.intent_dict,
        layers=3,
        vector_size=BACKEND['vector_size']
    )

    nll_loss = nn.CrossEntropyLoss()
    loss_weight = 0.0001
    center_loss = CenterLoss(d_model=2,
                             label_dict=data_loader.intent_dict)

    criterion = [nll_loss.cuda(), center_loss.cuda()]
    optimizer4nn = optim.Adam(model.parameters(), lr=0.0001, weight_decay=0.0005)

    optimzer4center = optim.SGD(center_loss.parameters(), lr=0.1)

    for epoch in range(5000):
        # print optimizer4nn.param_groups[0]['lr']
        train(train_data, model, criterion, [optimizer4nn, optimzer4center], BACKEND['batch_size'], loss_weight,
              data_loader.intent_dict)
        print(epoch)


if __name__ == '__main__':
    main()
