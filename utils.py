import torch
import matplotlib.pyplot as plt
from sklearn.metrics import (
    accuracy_score,
    classification_report,
)


def evaluate(model, criterion, data_loader, device):
    """
    Evalúa el modelo en los datos proporcionados y calcula la pérdida promedio.

    Args:
        model (torch.nn.Module): El modelo que se va a evaluar.
        criterion (torch.nn.Module): La función de pérdida que se utilizará para calcular la pérdida.
        data_loader (torch.utils.data.DataLoader): DataLoader que proporciona los datos de evaluación.

    Returns:
        float: La pérdida promedio en el conjunto de datos de evaluación.

    """
    model.eval()  # ponemos el modelo en modo de evaluacion
    total_loss = 0  # acumulador de la perdida
    with torch.no_grad():  # deshabilitamos el calculo de gradientes
        for x, y in data_loader:  # iteramos sobre el dataloader
            x = x.to(device)  # movemos los datos al dispositivo
            y = y.to(device)  # movemos los datos al dispositivo
            output = model(x)  # forward pass
            total_loss += criterion(output, y).item()  # acumulamos la perdida
    return total_loss / len(data_loader)  # retornamos la perdida promedio

def evaluate_unet(model, criterion, data_loader, device):
    intersection = 0
    denom = 0
    total = 0
    dice = 0.
    model.eval()  # ponemos el modelo en modo de evaluacion
    total_loss = 0  # acumulador de la perdida
    model.to(device)  # movemos el modelo al dispositivo
    with torch.no_grad():  # deshabilitamos el calculo de gradientes
        for x, y in data_loader:  # iteramos sobre el dataloader
            correct = 0
            intersection = 0
            denom = 0
            total = 0
            x = x.to(device=device, dtype = torch.float32)  # movemos los datos al dispositivo
            y = y.to(device=device, dtype = torch.long).squeeze(1)  # movemos los datos al dispositivo
            scores = model(x)  
            total_loss += criterion(scores, y).item()  # acumulamos la perdida
            # Calculamos estadísticas
            predictions = torch.argmax(scores, dim=1) # Obtenemos coordenadas de las predicciones
            correct += (predictions == y).sum() # Sumamos el número de predicciones correctas
            total += torch.numel(predictions) # Contamos el número total de predicciones

            # Calculamos el coeficiente de Dice
            # Al multiplicar las predicciones por los valores reales, obtenemos la intersección
            intersection += (predictions * y).sum()

            # Calculamos el denominador del coeficiente de Dice
            denom += (predictions + y).sum()

            # Obtenemos el valor del coeficiente de Dice (acumulado)
            dice = (2 * intersection) / (denom + 1e-8)

    return total_loss / len(data_loader), correct/total, dice.item()  # retornamos la perdida, accuracy y el dice promedio

class EarlyStopping:
    def __init__(self, patience=5):
        """
        Args:
            patience (int): Cuántas épocas esperar después de la última mejora.
        """
        self.patience = patience
        self.counter = 0
        self.best_score = float("inf")
        self.val_loss_min = float("inf")
        self.early_stop = False

    def __call__(self, val_loss):
        if val_loss > self.best_score:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True
        else:
            self.best_score = val_loss
            self.counter = 0

class EarlyStoppingForUnet:
    def __init__(self, patience=5):
        """
        Args:
            patience (int): Cuántas épocas esperar después de la última mejora.
            Considera el dice como parámetro para parar el entrenamiento.
        """
        self.patience = patience
        self.counter = 0
        self.best_score = 0.
        self.val_loss_min = float("inf")
        self.early_stop = False

    def __call__(self, dice):
        if dice < self.best_score:
            self.counter += 1
            print(f"Se incrementó counter early stop: {self.counter}")
            if self.counter >= self.patience:
                self.early_stop = True
        else:
            self.best_score = dice
            self.counter = 0
            print(f"Se actulizó best dice: {self.best_score:0.4f}")

def print_log(epoch, train_loss, val_loss):
    print(
        f"Epoch: {epoch + 1:03d} | Train Loss: {train_loss:.5f} | Val Loss: {val_loss:.5f}"
    )

def print_log_unet(epoch, train_loss, val_loss, accuracy, dice):
    print(
        f"Epoch: {epoch + 1:03d} | Train Loss: {train_loss:.5f} | Val Loss: {val_loss:.5f} | Accuracy: {accuracy:.5f} | Dice: {dice:.5f}"
    )

def train(
    model,
    optimizer,
    criterion,
    train_loader,
    val_loader,
    device,
    do_early_stopping=True,
    patience=5,
    epochs=10,
    log_fn=print_log,
    log_every=1,
):
    """
    Entrena el modelo utilizando el optimizador y la función de pérdida proporcionados.

    Args:
        model (torch.nn.Module): El modelo que se va a entrenar.
        optimizer (torch.optim.Optimizer): El optimizador que se utilizará para actualizar los pesos del modelo.
        criterion (torch.nn.Module): La función de pérdida que se utilizará para calcular la pérdida.
        train_loader (torch.utils.data.DataLoader): DataLoader que proporciona los datos de entrenamiento.
        val_loader (torch.utils.data.DataLoader): DataLoader que proporciona los datos de validación.
        device (str): El dispositivo donde se ejecutará el entrenamiento.
        patience (int): Número de épocas a esperar después de la última mejora en val_loss antes de detener el entrenamiento (default: 5).
        epochs (int): Número de épocas de entrenamiento (default: 10).
        log_fn (function): Función que se llamará después de cada log_every épocas con los argumentos (epoch, train_loss, val_loss) (default: None).
        log_every (int): Número de épocas entre cada llamada a log_fn (default: 1).

    Returns:
        Tuple[List[float], List[float]]: Una tupla con dos listas, la primera con el error de entrenamiento de cada época y la segunda con el error de validación de cada época.

    """
    epoch_train_errors = []  # colectamos el error de traing para posterior analisis
    epoch_val_errors = []  # colectamos el error de validacion para posterior analisis
    if do_early_stopping:
        early_stopping = EarlyStopping(
            patience=patience
        )  # instanciamos el early stopping

    for epoch in range(epochs):  # loop de entrenamiento
        model.train()  # ponemos el modelo en modo de entrenamiento
        train_loss = 0  # acumulador de la perdida de entrenamiento
        for x, y in train_loader:
            x = x.to(device)  # movemos los datos al dispositivo
            y = y.to(device)  # movemos los datos al dispositivo

            optimizer.zero_grad()  # reseteamos los gradientes

            output = model(x)  # forward pass (prediccion)
            batch_loss = criterion(
                output, y
            )  # calculamos la perdida con la salida esperada

            batch_loss.backward()  # backpropagation
            optimizer.step()  # actualizamos los pesos

            train_loss += batch_loss.item()  # acumulamos la perdida

        train_loss /= len(train_loader)  # calculamos la perdida promedio de la epoca
        epoch_train_errors.append(train_loss)  # guardamos la perdida de entrenamiento
        val_loss = evaluate(
            model, criterion, val_loader, device
        )  # evaluamos el modelo en el conjunto de validacion
        epoch_val_errors.append(val_loss)  # guardamos la perdida de validacion

        if do_early_stopping:
            early_stopping(val_loss)  # llamamos al early stopping

        if log_fn is not None:  # si se pasa una funcion de log
            if (epoch + 1) % log_every == 0:  # loggeamos cada log_every epocas
                log_fn(epoch, train_loss, val_loss)  # llamamos a la funcion de log

        if do_early_stopping and early_stopping.early_stop:
            print(
                f"Detener entrenamiento en la época {epoch}, la mejor pérdida fue {early_stopping.best_score:.5f}"
            )
            break

    return epoch_train_errors, epoch_val_errors



def train_unet(
    model,
    optimizer,
    criterion,
    train_loader,
    val_loader,
    device,
    do_early_stopping=True,
    patience=5,
    epochs=10,
    log_fn=print_log_unet,
    log_every=1,
):
    """
    Entrena el modelo utilizando el optimizador y la función de pérdida proporcionados.

    Args:
        model (torch.nn.Module): El modelo que se va a entrenar.
        optimizer (torch.optim.Optimizer): El optimizador que se utilizará para actualizar los pesos del modelo.
        criterion (torch.nn.Module): La función de pérdida que se utilizará para calcular la pérdida.
        train_loader (torch.utils.data.DataLoader): DataLoader que proporciona los datos de entrenamiento.
        val_loader (torch.utils.data.DataLoader): DataLoader que proporciona los datos de validación.
        device (str): El dispositivo donde se ejecutará el entrenamiento.
        epochs (int): Número de épocas de entrenamiento (default: 10).
        log_fn (function): Función que se llamará después de cada log_every épocas con los argumentos (epoch, train_loss, val_loss) (default: None).
        log_every (int): Número de épocas entre cada llamada a log_fn (default: 1).

    Returns:
        Tuple[List[float], List[float]]: Una tupla con dos listas, la primera con el error de entrenamiento de cada época y la segunda con el error de validación de cada época.

    """
    epoch_train_errors = []  # colectamos el error de traing para posterior analisis
    epoch_val_errors = []  # colectamos el error de validacion para posterior analisis
    epoch_dice_values = [] # Colectamos la evolución del valor dice
    epoc_acc = [] # Colectamos la evolución de la precisión

    if do_early_stopping:
        early_stopping = EarlyStoppingForUnet(
            patience=patience
        )  # instanciamos el early stopping

    for epoch in range(epochs):  # loop de entrenamiento
        model.train()  # ponemos el modelo en modo de entrenamiento
        train_loss = 0  # acumulador de la perdida de entrenamiento

        train_correct_num = 0
        train_total = 0
        train_cost_acum = 0.
        for x, y in train_loader:
            x = x.to(device=device, dtype=torch.float32)  # movemos los datos al dispositivo
            y = y.to(device=device, dtype=torch.long).squeeze(1)  # movemos los datos al dispositivo

            output = model(x)  # forward pass (prediccion)
            batch_loss = criterion(
                output, y
            )  # calculamos la perdida con la salida esperada
            optimizer.zero_grad()  # reseteamos los gradientes
            batch_loss.backward()  # backpropagation
            optimizer.step()  # actualizamos los pesos
            
            # Calculamos estadísticas
            # Al obtener 2 canales de salida, cada uno posee la probabilidad de pertenecer
            # a la clase o no. Por lo tanto, cada canal va a representar una clase.
            # Al obtener el "argmax", estamos indicando que clase tiene la mayor probabilidad
            # Y por tanto, es la predicción.
            train_predictions = torch.argmax(output, dim=1)
            train_correct_num += (train_predictions == y).sum() # Sumamos el número de predicciones correctas
            train_total += torch.numel(train_predictions) # Contamos el número total de predicciones
            train_loss += batch_loss.item()  # acumulamos la perdida

        train_loss /= len(train_loader)  # calculamos la perdida promedio de la epoca
        epoch_train_errors.append(train_loss)  # guardamos la perdida de entrenamiento
        
        train_acc = float(train_correct_num / train_total)
        epoc_acc.append(train_acc)

        val_loss, accuracy, dice = evaluate_unet(
                    model, criterion, val_loader, device
                )
        
        epoch_val_errors.append(val_loss)  # guardamos la perdida de validacion
        epoch_dice_values.append(dice) # guardamos el dice de la época

        if do_early_stopping:
          early_stopping(dice)  # llamamos al early stopping

        if log_fn is not None:  # si se pasa una funcion de log
            if (epoch + 1) % log_every == 0:  # loggeamos cada log_every epocas
                log_fn(epoch, train_loss, val_loss, accuracy, dice)  # llamamos a la funcion de log


        if do_early_stopping and early_stopping.early_stop:
            print(
                f"Detener entrenamiento en la época {epoch}, la mejor pérdida fue {early_stopping.best_score:.5f}"
            )
            break


    return epoch_train_errors, epoch_val_errors, epoch_dice_values

def train_unet_with_scheduler(
    model,
    optimizer,
    scheduler,
    criterion,
    train_loader,
    val_loader,
    device,
    do_early_stopping=True,
    patience=5,
    epochs=10,
    log_fn=print_log_unet,
    log_every=1,
):
    """
    Entrena el modelo utilizando el optimizador y la función de pérdida proporcionados.

    Args:
        model (torch.nn.Module): El modelo que se va a entrenar.
        optimizer (torch.optim.Optimizer): El optimizador que se utilizará para actualizar los pesos del modelo.
        criterion (torch.nn.Module): La función de pérdida que se utilizará para calcular la pérdida.
        train_loader (torch.utils.data.DataLoader): DataLoader que proporciona los datos de entrenamiento.
        val_loader (torch.utils.data.DataLoader): DataLoader que proporciona los datos de validación.
        device (str): El dispositivo donde se ejecutará el entrenamiento.
        epochs (int): Número de épocas de entrenamiento (default: 10).
        log_fn (function): Función que se llamará después de cada log_every épocas con los argumentos (epoch, train_loss, val_loss) (default: None).
        log_every (int): Número de épocas entre cada llamada a log_fn (default: 1).

    Returns:
        Tuple[List[float], List[float]]: Una tupla con dos listas, la primera con el error de entrenamiento de cada época y la segunda con el error de validación de cada época.

    """
    epoch_train_errors = []  # colectamos el error de traing para posterior analisis
    epoch_val_errors = []  # colectamos el error de validacion para posterior analisis
    epoch_dice_values = [] # Colectamos la evolución del valor dice
    epoc_acc = [] # Colectamos la evolución de la precisión

    if do_early_stopping:
        early_stopping = EarlyStoppingForUnet(
            patience=patience
        )  # instanciamos el early stopping

    for epoch in range(epochs):  # loop de entrenamiento
        model.train()  # ponemos el modelo en modo de entrenamiento
        train_loss = 0  # acumulador de la perdida de entrenamiento

        train_correct_num = 0
        train_total = 0
        train_cost_acum = 0.
        for x, y in train_loader:
            x = x.to(device=device, dtype=torch.float32)  # movemos los datos al dispositivo
            y = y.to(device=device, dtype=torch.long).squeeze(1)  # movemos los datos al dispositivo

            output = model(x)  # forward pass (prediccion)
            batch_loss = criterion(
                output, y
            )  # calculamos la perdida con la salida esperada
            optimizer.zero_grad()  # reseteamos los gradientes
            batch_loss.backward()  # backpropagation
            optimizer.step()  # actualizamos los pesos
            if scheduler is not None:
                scheduler.step(batch_loss.item())
            
            # Calculamos estadísticas
            # Al obtener 2 canales de salida, cada uno posee la probabilidad de pertenecer
            # a la clase o no. Por lo tanto, cada canal va a representar una clase.
            # Al obtener el "argmax", estamos indicando que clase tiene la mayor probabilidad
            # Y por tanto, es la predicción.
            train_predictions = torch.argmax(output, dim=1)
            train_correct_num += (train_predictions == y).sum() # Sumamos el número de predicciones correctas
            train_total += torch.numel(train_predictions) # Contamos el número total de predicciones
            train_loss += batch_loss.item()  # acumulamos la perdida

        train_loss /= len(train_loader)  # calculamos la perdida promedio de la epoca
        epoch_train_errors.append(train_loss)  # guardamos la perdida de entrenamiento
        
        train_acc = float(train_correct_num / train_total)
        epoc_acc.append(train_acc)

        val_loss, accuracy, dice = evaluate_unet(
                    model, criterion, val_loader, device
                )
        
        epoch_val_errors.append(val_loss)  # guardamos la perdida de validacion
        epoch_dice_values.append(dice) # guardamos el dice de la época

        if do_early_stopping:
          early_stopping(dice)  # llamamos al early stopping

        if log_fn is not None:  # si se pasa una funcion de log
            if (epoch + 1) % log_every == 0:  # loggeamos cada log_every epocas
                log_fn(epoch, train_loss, val_loss, accuracy, dice)  # llamamos a la funcion de log


        if do_early_stopping and early_stopping.early_stop:
            print(
                f"Detener entrenamiento en la época {epoch}, la mejor pérdida fue {early_stopping.best_score:.5f}"
            )
            break


    return epoch_train_errors, epoch_val_errors, epoch_dice_values

def plot_training(train_errors, val_errors):
    # Graficar los errores
    plt.figure(figsize=(10, 5))  # Define el tamaño de la figura
    plt.plot(train_errors, label="Train Loss")  # Grafica la pérdida de entrenamiento
    plt.plot(val_errors, label="Validation Loss")  # Grafica la pérdida de validación
    plt.title("Training and Validation Loss")  # Título del gráfico
    plt.xlabel("Epochs")  # Etiqueta del eje X
    plt.ylabel("Loss")  # Etiqueta del eje Y
    plt.legend()  # Añade una leyenda
    plt.grid(True)  # Añade una cuadrícula para facilitar la visualización
    plt.show()  # Muestra el gráfico

def plot_training_of_unet(train_errors, val_errors, dice_values):
    # Graficar los errores
    plt.figure(figsize=(10, 5))  # Define el tamaño de la figura
    plt.plot(train_errors, label="Train Loss")  # Grafica la pérdida de entrenamiento
    plt.plot(val_errors, label="Validation Loss")  # Grafica la pérdida de validación
    plt.plot(dice_values, label="Dice")
    plt.title("Training and Validation Loss")  # Título del gráfico
    plt.xlabel("Epochs")  # Etiqueta del eje X
    plt.legend()  # Añade una leyenda
    plt.grid(True)  # Añade una cuadrícula para facilitar la visualización
    plt.show()  # Muestra el gráfico

def model_calassification_report(model, dataloader, device, nclasses):
    # Evaluación del modelo
    model.eval()

    all_preds = []
    all_labels = []

    with torch.no_grad():
        for inputs, labels in dataloader:
            inputs = inputs.to(device)
            outputs = model(inputs)
            preds = torch.argmax(outputs, dim=1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.numpy())

    # Calcular precisión (accuracy)
    accuracy = accuracy_score(all_labels, all_preds)
    print(f"Accuracy: {accuracy:.4f}\n")

    # Reporte de clasificación
    report = classification_report(
        all_labels, all_preds, target_names=[str(i) for i in range(nclasses)]
    )
    print("Reporte de clasificación:\n", report)


def show_tensor_image(tensor, title=None, vmin=None, vmax=None):
    """
    Muestra una imagen representada como un tensor.

    Args:
        tensor (torch.Tensor): Tensor que representa la imagen. Size puede ser (C, H, W).
        title (str, optional): Título de la imagen. Por defecto es None.
        vmin (float, optional): Valor mínimo para la escala de colores. Por defecto es None.
        vmax (float, optional): Valor máximo para la escala de colores. Por defecto es None.
    """
    # Check if the tensor is a grayscale image
    if tensor.shape[0] == 1:
        plt.imshow(tensor.squeeze(), cmap="gray", vmin=vmin, vmax=vmax)
    else:  # Assume RGB
        plt.imshow(tensor.permute(1, 2, 0), vmin=vmin, vmax=vmax)
    if title:
        plt.title(title)
    plt.axis("off")
    plt.show()


def show_tensor_images(tensors, titles=None, figsize=(15, 5), vmin=None, vmax=None):
    """
    Muestra una lista de imágenes representadas como tensores.

    Args:
        tensors (list): Lista de tensores que representan las imágenes. El tamaño de cada tensor puede ser (C, H, W).
        titles (list, optional): Lista de títulos para las imágenes. Por defecto es None.
        vmin (float, optional): Valor mínimo para la escala de colores. Por defecto es None.
        vmax (float, optional): Valor máximo para la escala de colores. Por defecto es None.
    """
    num_images = len(tensors)
    _, axs = plt.subplots(1, num_images, figsize=figsize)
    for i, tensor in enumerate(tensors):
        ax = axs[i]
        # Check if the tensor is a grayscale image
        if tensor.shape[0] == 1:
            ax.imshow(tensor.squeeze(), cmap="gray", vmin=vmin, vmax=vmax)
        else:  # Assume RGB
            ax.imshow(tensor.permute(1, 2, 0), vmin=vmin, vmax=vmax)
        if titles and titles[i]:
            ax.set_title(titles[i])
        ax.axis("off")
    plt.show()
